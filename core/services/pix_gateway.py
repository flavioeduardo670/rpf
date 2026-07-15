from __future__ import annotations

import hashlib
import hmac
import json
import base64
import logging
import re
import uuid
from io import BytesIO
from decimal import Decimal
from typing import Any
from urllib import error, parse, request

import segno
from django.conf import settings

logger = logging.getLogger('core.services.pix_gateway')
MERCADO_PAGO_API_BASE_URL = 'https://api.mercadopago.com'
STATUS_PAGO_MERCADO_PAGO = {'approved', 'accredited'}


def _pix_tlv(pid: str, value: Any) -> str:
    value = str(value)
    return f"{pid}{len(value):02d}{value}"


_DDDS_BRASIL = {
    '11', '12', '13', '14', '15', '16', '17', '18', '19',
    '21', '22', '24', '27', '28',
    '31', '32', '33', '34', '35', '37', '38',
    '41', '42', '43', '44', '45', '46', '47', '48', '49',
    '51', '53', '54', '55',
    '61', '62', '63', '64', '65', '66', '67', '68', '69',
    '71', '73', '74', '75', '77', '79',
    '81', '82', '83', '84', '85', '86', '87', '88', '89',
    '91', '92', '93', '94', '95', '96', '97', '98', '99',
}


def normalizar_chave_pix(chave_pix: str) -> str:
    chave = (chave_pix or '').strip()
    if not chave:
        return ''

    chave_sem_separadores = re.sub(r'[\s().-]+', '', chave)
    if chave.startswith('+'):
        return f"+{re.sub(r'\D', '', chave)}"

    if chave_sem_separadores.isdigit():
        if len(chave_sem_separadores) == 13 and chave_sem_separadores.startswith('55'):
            return f'+{chave_sem_separadores}'
        if (
            len(chave_sem_separadores) == 11
            and chave_sem_separadores[:2] in _DDDS_BRASIL
            and chave_sem_separadores[2] == '9'
        ):
            return f'+55{chave_sem_separadores}'

    return chave


def _pix_crc16(payload: str) -> str:
    data = (payload + '6304').encode('utf-8')
    crc = 0xFFFF
    for byte in data:
        crc ^= byte << 8
        for _ in range(8):
            if crc & 0x8000:
                crc = ((crc << 1) ^ 0x1021) & 0xFFFF
            else:
                crc = (crc << 1) & 0xFFFF
    return f"{crc:04X}"


def gerar_payload_pix(chave_pix: str, valor: Decimal, txid: str, *, nome_recebedor: str = 'REPUBLICA RPF', cidade: str = 'SAO PAULO') -> str:
    chave_pix = normalizar_chave_pix(chave_pix)
    merchant_account = _pix_tlv('00', 'br.gov.bcb.pix') + _pix_tlv('01', chave_pix)
    payload = (
        _pix_tlv('00', '01')
        + _pix_tlv('26', merchant_account)
        + _pix_tlv('52', '0000')
        + _pix_tlv('53', '986')
        + _pix_tlv('54', f"{Decimal(valor):.2f}")
        + _pix_tlv('58', 'BR')
        + _pix_tlv('59', nome_recebedor[:25].upper())
        + _pix_tlv('60', cidade[:15].upper())
        + _pix_tlv('62', _pix_tlv('05', txid))
    )
    return payload + '6304' + _pix_crc16(payload)


def gerar_qr_code_data_uri(payload_pix: str) -> str:
    if not payload_pix:
        return ''
    qr = segno.make(payload_pix, error='m')
    stream = BytesIO()
    qr.save(stream, kind='png', scale=8, border=2, dark='#000000', light='#FFFFFF')
    encoded = base64.b64encode(stream.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def _mercado_pago_access_token() -> str:
    return getattr(settings, 'MERCADOPAGO_ACCESS_TOKEN', '').strip()


def _mercado_pago_request(method: str, path: str, *, payload: dict[str, Any] | None = None, idempotency_key: str = '') -> dict[str, Any]:
    token = _mercado_pago_access_token()
    if not token:
        raise RuntimeError('MERCADOPAGO_ACCESS_TOKEN nao configurado.')

    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
    }
    if idempotency_key:
        headers['X-Idempotency-Key'] = idempotency_key

    req = request.Request(
        url=f"{MERCADO_PAGO_API_BASE_URL}{path}",
        headers=headers,
        data=json.dumps(payload).encode('utf-8') if payload is not None else None,
        method=method,
    )
    with request.urlopen(req, timeout=getattr(settings, 'MERCADOPAGO_TIMEOUT', 10)) as response:
        return json.loads(response.read().decode('utf-8'))


def _extrair_dados_pix_mercado_pago(data: dict[str, Any]) -> dict[str, str]:
    transaction_data = (data.get('point_of_interaction') or {}).get('transaction_data') or {}
    qr_code = transaction_data.get('qr_code') or ''
    qr_code_base64 = transaction_data.get('qr_code_base64') or ''
    return {
        'payload_pix': qr_code,
        'qr_code': qr_code,
        'qr_code_base64': qr_code_base64,
        'qr_code_data_uri': f'data:image/png;base64,{qr_code_base64}' if qr_code_base64 else gerar_qr_code_data_uri(qr_code),
        'ticket_url': transaction_data.get('ticket_url') or '',
    }


def _mapear_status_mercado_pago(status: str) -> str:
    status = (status or '').strip().lower()
    if status in STATUS_PAGO_MERCADO_PAGO:
        return 'pago'
    if status in {'cancelled', 'refunded', 'charged_back'}:
        return 'cancelado'
    if status in {'rejected'}:
        return 'rejeitado'
    return status or 'desconhecido'


def _fallback_pix_local(*, txid: str, valor: Decimal, chave_pix: str, categoria: str = '') -> dict[str, Any]:
    payload_pix = gerar_payload_pix(
        chave_pix=chave_pix,
        valor=valor,
        txid=txid,
        nome_recebedor='ASSOC CULT RPF',
        cidade='SAO PAULO',
    )
    return {
        'txid': txid,
        'payment_id': '',
        'payload_pix': payload_pix,
        'qr_code': payload_pix,
        'qr_code_base64': '',
        'ticket_url': '',
        'status_gateway': 'aguardando',
        'qr_code_url': '',
        'qr_code_data_uri': gerar_qr_code_data_uri(payload_pix),
        'provider_payload': {
            'modo': 'local',
            'payload_pix': payload_pix,
            'categoria': categoria,
        },
    }


def criar_cobranca_pix_avulsa(*, txid: str, valor: Decimal, chave_pix: str, nome_pagador: str = '', categoria: str = '') -> dict[str, Any]:
    if not _mercado_pago_access_token():
        logger.error('Mercado Pago nao configurado para criar cobranca PIX', extra={'event': 'pix.mercadopago.configuration_error', 'txid': txid})
        return _fallback_pix_local(txid=txid, valor=valor, chave_pix=chave_pix, categoria=categoria) if chave_pix else {
            'txid': txid,
            'payment_id': '',
            'payload_pix': '',
            'qr_code': '',
            'qr_code_base64': '',
            'ticket_url': '',
            'status_gateway': 'erro_configuracao',
            'qr_code_url': '',
            'qr_code_data_uri': '',
            'provider_payload': {'erro': 'mercadopago_access_token_nao_configurado'},
        }

    payer_email = getattr(settings, 'MERCADOPAGO_PAYER_EMAIL_FALLBACK', 'pagador@example.com')
    payload = {
        'transaction_amount': float(Decimal(valor).quantize(Decimal('0.01'))),
        'description': f'{categoria or "Cobranca"} - {nome_pagador or txid}',
        'payment_method_id': 'pix',
        'external_reference': txid,
        'payer': {'email': payer_email},
    }
    notification_url = getattr(settings, 'MERCADOPAGO_NOTIFICATION_URL', '').strip()
    if notification_url:
        payload['notification_url'] = notification_url

    try:
        data = _mercado_pago_request('POST', '/v1/payments', payload=payload, idempotency_key=f'rpf-{txid}-{uuid.uuid4()}')
        pix = _extrair_dados_pix_mercado_pago(data)
        logger.info('Cobranca PIX criada no Mercado Pago', extra={'event': 'pix.mercadopago.payment_created', 'txid': txid, 'payment_id': data.get('id'), 'status_gateway': data.get('status')})
        return {
            'txid': txid,
            'payment_id': str(data.get('id') or ''),
            'payload_pix': pix['payload_pix'],
            'qr_code': pix['qr_code'],
            'qr_code_base64': pix['qr_code_base64'],
            'ticket_url': pix['ticket_url'],
            'status_gateway': _mapear_status_mercado_pago(data.get('status') or ''),
            'qr_code_url': pix['ticket_url'],
            'qr_code_data_uri': pix['qr_code_data_uri'],
            'provider_payload': data,
        }
    except (RuntimeError, error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        logger.exception('Falha ao criar cobranca PIX no Mercado Pago', extra={'event': 'pix.mercadopago.payment_create_error', 'txid': txid})
        return _fallback_pix_local(txid=txid, valor=valor, chave_pix=chave_pix, categoria=categoria) if chave_pix else {
            'txid': txid,
            'payment_id': '',
            'payload_pix': '',
            'qr_code': '',
            'qr_code_base64': '',
            'ticket_url': '',
            'status_gateway': 'erro_gateway',
            'qr_code_url': '',
            'qr_code_data_uri': '',
            'provider_payload': {'erro': 'mercadopago_payment_create_error'},
        }


def criar_cobranca_pix(*, pedido, chave_pix: str) -> dict[str, Any]:
    txid = f"RPF{pedido.id:08d}"
    return criar_cobranca_pix_avulsa(
        txid=txid,
        valor=pedido.valor_total,
        chave_pix=chave_pix,
        nome_pagador=pedido.nome_comprador,
        categoria='Ingresso',
    )


def consultar_pagamento_mercado_pago(payment_id: str) -> dict[str, Any]:
    try:
        data = _mercado_pago_request('GET', f'/v1/payments/{payment_id}')
    except error.HTTPError as exc:
        if exc.code == 404:
            logger.warning('Pagamento Mercado Pago inexistente ignorado.', extra={'event': 'pix.mercadopago.payment_not_found', 'payment_id': payment_id})
            return {'txid': '', 'payment_id': str(payment_id or ''), 'status': 'nao_encontrado', 'status_gateway': 'nao_encontrado', 'provider_payload': {'erro': 'payment_not_found'}}
        raise
    pix = _extrair_dados_pix_mercado_pago(data)
    return {
        'txid': data.get('external_reference') or '',
        'payment_id': str(data.get('id') or payment_id),
        'status': _mapear_status_mercado_pago(data.get('status') or ''),
        'status_gateway': _mapear_status_mercado_pago(data.get('status') or ''),
        'payload_pix': pix['payload_pix'],
        'qr_code': pix['qr_code'],
        'qr_code_base64': pix['qr_code_base64'],
        'ticket_url': pix['ticket_url'],
        'provider_payload': data,
    }


def consultar_merchant_order_mercado_pago(order_id: str) -> dict[str, Any]:
    try:
        data = _mercado_pago_request('GET', f'/merchant_orders/{order_id}')
    except error.HTTPError as exc:
        if exc.code == 404:
            logger.warning('Merchant order Mercado Pago inexistente ignorada.', extra={'event': 'pix.mercadopago.merchant_order_not_found', 'order_id': order_id})
            return {'txid': '', 'payment_id': '', 'status': 'nao_encontrado', 'status_gateway': 'nao_encontrado', 'provider_payload': {'erro': 'merchant_order_not_found'}}
        raise

    payments = data.get('payments') or []
    approved_payment = next((payment for payment in payments if (payment.get('status') or '').lower() in STATUS_PAGO_MERCADO_PAGO), None)
    payment = approved_payment or (payments[0] if payments else {})
    payment_id = str(payment.get('id') or '')
    status = _mapear_status_mercado_pago(payment.get('status') or data.get('status') or '')
    return {
        'txid': data.get('external_reference') or payment.get('external_reference') or '',
        'payment_id': payment_id,
        'status': status,
        'status_gateway': status,
        'provider_payload': data,
    }


def consultar_evento_mercado_pago(resource_id: str, event_type: str = '') -> dict[str, Any]:
    event_type = (event_type or '').strip().lower()
    if event_type == 'payment':
        return consultar_pagamento_mercado_pago(resource_id)
    if event_type == 'merchant_order':
        return consultar_merchant_order_mercado_pago(resource_id)
    if event_type == 'order':
        logger.warning('Evento order do Mercado Pago ignorado; pagamentos PIX sao processados via payment ou merchant_order.', extra={'event': 'pix.mercadopago.order_ignored', 'order_id': resource_id})
        return {'txid': '', 'payment_id': '', 'status': 'ignorado', 'status_gateway': 'ignorado', 'provider_payload': {'tipo': 'order', 'id': resource_id}}
    logger.warning('Tipo de evento Mercado Pago desconhecido; tentativa como payment.', extra={'event': 'pix.mercadopago.event_type_unknown', 'event_type': event_type, 'resource_id': resource_id})
    return consultar_pagamento_mercado_pago(resource_id)


def consultar_status_por_txid(txid: str) -> dict[str, Any]:
    if not _mercado_pago_access_token():
        logger.warning('Consulta de status PIX sem Mercado Pago configurado', extra={'event': 'pix.mercadopago.status.configuration_missing', 'txid': txid})
        return {'txid': txid, 'status': 'desconhecido'}

    try:
        query = parse.urlencode({'external_reference': txid})
        data = _mercado_pago_request('GET', f'/v1/payments/search?{query}')
        results = data.get('results') or []
        if not results:
            return {'txid': txid, 'status': 'desconhecido', 'provider_payload': data}
        payment = sorted(results, key=lambda item: item.get('date_created') or '', reverse=True)[0]
        payment_id = str(payment.get('id') or '')
        if payment_id:
            return consultar_pagamento_mercado_pago(payment_id)
        return {
            'txid': txid,
            'status': _mapear_status_mercado_pago(payment.get('status') or ''),
            'provider_payload': payment,
        }
    except (RuntimeError, error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        logger.exception('Falha ao consultar status PIX no Mercado Pago', extra={'event': 'pix.mercadopago.status_error', 'txid': txid})
        return {'txid': txid, 'status': 'desconhecido'}


def validar_assinatura_webhook(body: bytes, assinatura_informada: str, *, request_id: str = '', data_id: str = '') -> bool:
    secret = getattr(settings, 'MERCADOPAGO_WEBHOOK_SECRET', '').strip()
    if not secret:
        return True
    partes = {}
    for parte in (assinatura_informada or '').split(','):
        if '=' in parte:
            chave, valor = parte.split('=', 1)
            partes[chave.strip()] = valor.strip()
    ts = partes.get('ts') or ''
    v1 = partes.get('v1') or ''
    manifest = ''
    if data_id:
        manifest += f'id:{data_id};'
    if request_id:
        manifest += f'request-id:{request_id};'
    if ts:
        manifest += f'ts:{ts};'
    if not manifest or not v1:
        return False
    assinatura = hmac.new(secret.encode('utf-8'), manifest.encode('utf-8'), hashlib.sha256).hexdigest()
    return hmac.compare_digest(assinatura, v1)

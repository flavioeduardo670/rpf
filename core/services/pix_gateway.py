from __future__ import annotations

import hashlib
import hmac
import json
import base64
import logging
from io import BytesIO
from decimal import Decimal
from typing import Any
from urllib import error, request

import segno
from django.conf import settings

logger = logging.getLogger('core.services.pix_gateway')


def _pix_tlv(pid: str, value: Any) -> str:
    value = str(value)
    return f"{pid}{len(value):02d}{value}"


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


def _gerar_payload_pix(chave_pix: str, valor: Decimal, txid: str) -> str:
    merchant_account = _pix_tlv('00', 'br.gov.bcb.pix') + _pix_tlv('01', chave_pix)
    payload = (
        _pix_tlv('00', '01')
        + _pix_tlv('26', merchant_account)
        + _pix_tlv('52', '0000')
        + _pix_tlv('53', '986')
        + _pix_tlv('54', f"{Decimal(valor):.2f}")
        + _pix_tlv('58', 'BR')
        + _pix_tlv('59', 'REPUBLICA RPF')
        + _pix_tlv('60', 'SAO PAULO')
        + _pix_tlv('62', _pix_tlv('05', txid))
    )
    return payload + '6304' + _pix_crc16(payload)


def _gerar_qr_code_data_uri(payload_pix: str) -> str:
    if not payload_pix:
        return ''
    qr = segno.make(payload_pix, error='m')
    stream = BytesIO()
    qr.save(stream, kind='png', scale=8, border=2, dark='#000000', light='#FFFFFF')
    encoded = base64.b64encode(stream.getvalue()).decode('ascii')
    return f'data:image/png;base64,{encoded}'


def criar_cobranca_pix(*, pedido, chave_pix: str) -> dict[str, Any]:
    txid = f"RPF{pedido.id:08d}"
    if not chave_pix:
        logger.error(
            'Chave PIX nao configurada para criar cobranca',
            extra={'event': 'pix.charge.configuration_error', 'pedido_id': pedido.id, 'txid': txid},
        )
        return {
            'txid': txid,
            'payload_pix': '',
            'status_gateway': 'erro_configuracao',
            'qr_code_url': '',
            'qr_code_data_uri': '',
            'provider_payload': {'erro': 'chave_pix_nao_configurada'},
        }

    payload_pix = _gerar_payload_pix(chave_pix=chave_pix, valor=pedido.valor_total, txid=txid)
    fallback = {
        'txid': txid,
        'payload_pix': payload_pix,
        'status_gateway': 'aguardando',
        'qr_code_url': '',
        'qr_code_data_uri': _gerar_qr_code_data_uri(payload_pix),
        'provider_payload': {
            'modo': 'local',
            'payload_pix': payload_pix,
        },
    }

    base_url = getattr(settings, 'PIX_PSP_BASE_URL', '').strip()
    token = getattr(settings, 'PIX_PSP_API_TOKEN', '').strip()
    if not base_url or not token:
        logger.warning(
            'Gateway PIX nao configurado. Usando modo local',
            extra={'event': 'pix.charge.local_mode', 'pedido_id': pedido.id, 'txid': txid},
        )
        return fallback

    try:
        req = request.Request(
            url=f"{base_url.rstrip('/')}/pix/cobrancas",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            data=json.dumps({
                'txid': txid,
                'valor': f"{pedido.valor_total:.2f}",
                'nome_comprador': pedido.nome_comprador,
            }).encode('utf-8'),
            method='POST',
        )
        with request.urlopen(req, timeout=getattr(settings, 'PIX_PSP_TIMEOUT', 10)) as response:
            data = json.loads(response.read().decode('utf-8'))
        logger.info(
            'Cobranca PIX criada via PSP',
            extra={
                'event': 'pix.charge.created',
                'pedido_id': pedido.id,
                'txid': data.get('txid') or txid,
                'status_gateway': data.get('status', 'aguardando'),
            },
        )
        return {
            'txid': data.get('txid') or txid,
            'payload_pix': data.get('payload_pix') or payload_pix,
            'status_gateway': data.get('status', 'aguardando'),
            'qr_code_url': '',
            'qr_code_data_uri': fallback['qr_code_data_uri'],
            'provider_payload': data,
        }
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        logger.exception(
            'Falha ao criar cobranca no PSP. Aplicando fallback local',
            extra={'event': 'pix.charge.gateway_error', 'pedido_id': pedido.id, 'txid': txid},
        )
        return fallback


def consultar_status_por_txid(txid: str) -> dict[str, Any]:
    base_url = getattr(settings, 'PIX_PSP_BASE_URL', '').strip()
    token = getattr(settings, 'PIX_PSP_API_TOKEN', '').strip()
    if not base_url or not token:
        logger.warning(
            'Consulta de status PIX sem configuracao de gateway',
            extra={'event': 'pix.status.configuration_missing', 'txid': txid},
        )
        return {'txid': txid, 'status': 'desconhecido'}

    try:
        req = request.Request(
            url=f"{base_url.rstrip('/')}/pix/cobrancas/{txid}",
            headers={'Authorization': f'Bearer {token}'},
            method='GET',
        )
        with request.urlopen(req, timeout=getattr(settings, 'PIX_PSP_TIMEOUT', 10)) as response:
            data = json.loads(response.read().decode('utf-8'))
        logger.info(
            'Status PIX consultado com sucesso',
            extra={'event': 'pix.status.checked', 'txid': data.get('txid', txid), 'status_gateway': data.get('status', 'desconhecido')},
        )
        return {
            'txid': data.get('txid', txid),
            'status': data.get('status', 'desconhecido'),
            'provider_payload': data,
        }
    except (error.HTTPError, error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
        logger.exception(
            'Falha ao consultar status PIX no PSP',
            extra={'event': 'pix.status.gateway_error', 'txid': txid},
        )
        return {'txid': txid, 'status': 'desconhecido'}


def validar_assinatura_webhook(body: bytes, assinatura_informada: str) -> bool:
    secret = getattr(settings, 'PIX_WEBHOOK_SECRET', '').encode('utf-8')
    if not secret:
        return False
    assinatura = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(assinatura, (assinatura_informada or '').strip())

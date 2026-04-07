from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal
from typing import Any
from urllib.parse import quote

import requests
from django.conf import settings


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


def criar_cobranca_pix(*, pedido, chave_pix: str) -> dict[str, Any]:
    txid = f"RPF{pedido.id:08d}"
    if not chave_pix:
        return {
            'txid': txid,
            'payload_pix': '',
            'status_gateway': 'erro_configuracao',
            'qr_code_url': '',
            'provider_payload': {'erro': 'chave_pix_nao_configurada'},
        }

    payload_pix = _gerar_payload_pix(chave_pix=chave_pix, valor=pedido.valor_total, txid=txid)
    fallback = {
        'txid': txid,
        'payload_pix': payload_pix,
        'status_gateway': 'aguardando',
        'qr_code_url': f"https://api.qrserver.com/v1/create-qr-code/?size=300x300&data={quote(payload_pix)}",
        'provider_payload': {
            'modo': 'local',
            'payload_pix': payload_pix,
        },
    }

    base_url = getattr(settings, 'PIX_PSP_BASE_URL', '').strip()
    token = getattr(settings, 'PIX_PSP_API_TOKEN', '').strip()
    if not base_url or not token:
        return fallback

    try:
        resp = requests.post(
            f"{base_url.rstrip('/')}/pix/cobrancas",
            headers={
                'Authorization': f'Bearer {token}',
                'Content-Type': 'application/json',
            },
            json={
                'txid': txid,
                'valor': f"{pedido.valor_total:.2f}",
                'nome_comprador': pedido.nome_comprador,
            },
            timeout=getattr(settings, 'PIX_PSP_TIMEOUT', 10),
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'txid': data.get('txid') or txid,
            'payload_pix': data.get('payload_pix') or payload_pix,
            'status_gateway': data.get('status', 'aguardando'),
            'qr_code_url': data.get('qr_code_url') or fallback['qr_code_url'],
            'provider_payload': data,
        }
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        return fallback


def consultar_status_por_txid(txid: str) -> dict[str, Any]:
    base_url = getattr(settings, 'PIX_PSP_BASE_URL', '').strip()
    token = getattr(settings, 'PIX_PSP_API_TOKEN', '').strip()
    if not base_url or not token:
        return {'txid': txid, 'status': 'desconhecido'}

    try:
        resp = requests.get(
            f"{base_url.rstrip('/')}/pix/cobrancas/{txid}",
            headers={'Authorization': f'Bearer {token}'},
            timeout=getattr(settings, 'PIX_PSP_TIMEOUT', 10),
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            'txid': data.get('txid', txid),
            'status': data.get('status', 'desconhecido'),
            'provider_payload': data,
        }
    except (requests.RequestException, ValueError, json.JSONDecodeError):
        return {'txid': txid, 'status': 'desconhecido'}


def validar_assinatura_webhook(body: bytes, assinatura_informada: str) -> bool:
    secret = getattr(settings, 'PIX_WEBHOOK_SECRET', '').encode('utf-8')
    if not secret:
        return False
    assinatura = hmac.new(secret, body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(assinatura, (assinatura_informada or '').strip())

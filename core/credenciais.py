"""Credenciais de cada cliente (token do Mercado Pago etc.) guardadas cifradas no banco.

A chave vem de ``CREDENCIAIS_CHAVE`` (variável de ambiente, recomendada) ou, na
falta dela, é derivada da ``SECRET_KEY``. Atenção: trocar a SECRET_KEY sem ter
definido CREDENCIAIS_CHAVE torna as credenciais salvas ilegíveis (elas teriam de
ser cadastradas de novo).
"""
import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings


def _fernet():
    chave = (getattr(settings, 'CREDENCIAIS_CHAVE', '') or '').strip()
    if not chave:
        chave = base64.urlsafe_b64encode(hashlib.sha256(f'credenciais:{settings.SECRET_KEY}'.encode()).digest()).decode()
    return Fernet(chave.encode())


def cifrar(texto: str) -> str:
    texto = (texto or '').strip()
    return _fernet().encrypt(texto.encode()).decode() if texto else ''


def decifrar(cifrado: str) -> str:
    if not cifrado:
        return ''
    try:
        return _fernet().decrypt(cifrado.encode()).decode()
    except (InvalidToken, ValueError):
        return ''


def mascarar(texto: str) -> str:
    """'APP_USR-...1234' para mostrar no Admin sem expor o segredo."""
    if not texto:
        return ''
    return f'{texto[:8]}…{texto[-4:]}' if len(texto) > 16 else '••••'

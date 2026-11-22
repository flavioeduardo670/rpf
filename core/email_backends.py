"""Envio de email por API HTTPS.

O plano gratuito do Render bloqueia conexões SMTP de saída (portas 25, 465 e
587): a conexão fica pendurada até o gunicorn derrubar o processo. A API
transacional do Brevo usa HTTPS (porta 443), que não é bloqueada.

Ativado definindo ``BREVO_API_KEY`` (ver ``rpf/settings.py``).
"""
from __future__ import annotations

import base64
import json
import logging
from email.utils import parseaddr
from urllib import error, request

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger('core.email')
BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'


def _contato(endereco: str) -> dict:
    nome, email = parseaddr(endereco or '')
    contato = {'email': email or endereco}
    if nome:
        contato['name'] = nome
    return contato


class BrevoEmailBackend(BaseEmailBackend):
    def __init__(self, fail_silently=False, api_key=None, timeout=None, **kwargs):
        super().__init__(fail_silently=fail_silently, **kwargs)
        self.api_key = api_key or getattr(settings, 'BREVO_API_KEY', '')
        self.timeout = timeout or getattr(settings, 'EMAIL_TIMEOUT', None) or 10

    def _payload(self, mensagem) -> dict:
        payload = {
            'sender': _contato(mensagem.from_email or settings.DEFAULT_FROM_EMAIL),
            'to': [_contato(destino) for destino in mensagem.to],
            'subject': mensagem.subject,
        }
        if mensagem.cc:
            payload['cc'] = [_contato(destino) for destino in mensagem.cc]
        if mensagem.bcc:
            payload['bcc'] = [_contato(destino) for destino in mensagem.bcc]
        if mensagem.reply_to:
            payload['replyTo'] = _contato(mensagem.reply_to[0])
        if getattr(mensagem, 'content_subtype', 'plain') == 'html':
            payload['htmlContent'] = mensagem.body
        else:
            payload['textContent'] = mensagem.body
        for alternativa, tipo in getattr(mensagem, 'alternatives', []) or []:
            if tipo == 'text/html':
                payload['htmlContent'] = alternativa
        anexos = []
        for anexo in mensagem.attachments:
            if isinstance(anexo, tuple):
                nome, conteudo, _tipo = anexo
            else:  # MIMEBase
                nome = anexo.get_filename()
                conteudo = anexo.get_payload(decode=True)
            if isinstance(conteudo, str):
                conteudo = conteudo.encode('utf-8')
            anexos.append({'name': nome, 'content': base64.b64encode(conteudo).decode('ascii')})
        if anexos:
            payload['attachment'] = anexos
        return payload

    def send_messages(self, email_messages):
        if not email_messages:
            return 0
        if not self.api_key:
            if self.fail_silently:
                return 0
            raise RuntimeError('BREVO_API_KEY nao configurada.')
        enviados = 0
        for mensagem in email_messages:
            if not mensagem.recipients():
                continue
            req = request.Request(
                BREVO_API_URL,
                data=json.dumps(self._payload(mensagem)).encode('utf-8'),
                headers={'api-key': self.api_key, 'Content-Type': 'application/json', 'Accept': 'application/json'},
                method='POST',
            )
            try:
                with request.urlopen(req, timeout=self.timeout) as resposta:
                    resposta.read()
                enviados += 1
            except error.HTTPError as exc:
                detalhe = exc.read().decode('utf-8', 'replace')[:300]
                logger.error('Brevo recusou o email.', extra={'event': 'email.brevo.http_error', 'http_status': exc.code, 'detalhe': detalhe})
                if not self.fail_silently:
                    raise RuntimeError(f'Brevo recusou o email (HTTP {exc.code}): {detalhe}') from exc
            except (error.URLError, TimeoutError, OSError):
                if not self.fail_silently:
                    raise
        return enviados

"""Confirmação de pagamento do aluguel e envio do recibo.

Ponto único usado pelo webhook do Mercado Pago, pela tela do financeiro e pelo
comando ``verificar_pagamentos_aluguel``. Assim as três rotas marcam a cobrança
como paga do mesmo jeito e o recibo só é dado como enviado quando o email sai
de fato.
"""
from __future__ import annotations

import logging
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from core.models import CobrancaAluguel, Mensalidade
from core.services.pix_gateway import cancelar_pagamento_mercado_pago, consultar_status_por_txid, mercado_pago_configurado

logger = logging.getLogger('core.services.aluguel')

STATUS_PAGO = {'pago', 'paid', 'concluido', 'approved', 'accredited'}
# Recibos de pagamentos mais antigos que isso não são reenviados
# automaticamente (ex.: morador que só cadastrou o email meses depois).
JANELA_REENVIO_COMPROVANTE = timedelta(days=45)


def status_indica_pagamento(status: str) -> bool:
    return (status or '').strip().lower() in STATUS_PAGO


def enviar_comprovante_se_pendente(cobranca: CobrancaAluguel) -> bool:
    """Envia o recibo uma única vez. Falhas ficam para a próxima tentativa."""
    if cobranca.status != 'pago' or cobranca.comprovante_enviado_em:
        return False
    from core.views.financeiro import enviar_comprovante_aluguel_por_email

    try:
        enviado = enviar_comprovante_aluguel_por_email(cobranca)
    except Exception:
        logger.exception(
            'Falha ao enviar comprovante de aluguel por email; nova tentativa na proxima verificacao.',
            extra={'event': 'aluguel.comprovante.erro_envio', 'cobranca_id': cobranca.id},
        )
        return False
    if not enviado:
        logger.warning(
            'Morador sem email cadastrado; comprovante de aluguel nao enviado.',
            extra={'event': 'aluguel.comprovante.sem_email', 'cobranca_id': cobranca.id, 'morador_id': cobranca.morador_id},
        )
        return False
    cobranca.comprovante_enviado_em = timezone.now()
    cobranca.save(update_fields=['comprovante_enviado_em', 'atualizado_em'])
    logger.info('Comprovante de aluguel enviado.', extra={'event': 'aluguel.comprovante.enviado', 'cobranca_id': cobranca.id})
    return True


def confirmar_pagamento_aluguel(
    cobranca: CobrancaAluguel,
    *,
    status_gateway: str = 'pago',
    provider_payload: dict | None = None,
    payment_id: str = '',
) -> bool:
    """Marca a cobrança como paga, quita a mensalidade e envia o recibo.

    Retorna True só na primeira confirmação (é idempotente: webhooks repetidos
    e a verificação periódica podem chamar várias vezes).
    """
    with transaction.atomic():
        atual = CobrancaAluguel.objects.select_for_update().select_related('morador').get(pk=cobranca.pk)
        if atual.status == 'pago':
            confirmada = False
        else:
            agora = timezone.now()
            atual.status = 'pago'
            atual.pago_em = agora
            atual.status_gateway = status_gateway or atual.status_gateway
            if provider_payload is not None:
                atual.provider_payload = provider_payload
            if payment_id:
                atual.payment_id = payment_id
            atual.save(update_fields=['status', 'pago_em', 'status_gateway', 'provider_payload', 'payment_id', 'atualizado_em'])
            Mensalidade.objects.update_or_create(
                morador=atual.morador,
                mes_referencia=atual.mes_referencia,
                defaults={'valor': atual.valor, 'pago': True, 'data_pagamento': timezone.localdate(agora)},
            )
            confirmada = True
            logger.info('Pagamento de aluguel confirmado.', extra={'event': 'aluguel.pagamento.confirmado', 'cobranca_id': atual.id, 'payment_id': atual.payment_id})

    enviar_comprovante_se_pendente(atual)
    # Mantém o objeto de quem chamou coerente com o banco.
    for campo in ('status', 'pago_em', 'status_gateway', 'provider_payload', 'payment_id', 'comprovante_enviado_em'):
        setattr(cobranca, campo, getattr(atual, campo))
    return confirmada


def verificar_cobranca_no_gateway(cobranca: CobrancaAluguel) -> bool:
    """Consulta o Mercado Pago pelo TXID e confirma se já foi pago."""
    if cobranca.status != 'aguardando_pagamento' or not cobranca.txid:
        return False
    resultado = consultar_status_por_txid(cobranca.txid)
    status = resultado.get('status') or ''
    provider_payload = resultado.get('provider_payload') or resultado
    if status_indica_pagamento(status):
        return confirmar_pagamento_aluguel(
            cobranca,
            status_gateway=status,
            provider_payload=provider_payload,
            payment_id=resultado.get('payment_id') or '',
        )
    if status and status != 'desconhecido' and status != cobranca.status_gateway:
        cobranca.status_gateway = status
        cobranca.provider_payload = provider_payload
        cobranca.save(update_fields=['status_gateway', 'provider_payload', 'atualizado_em'])
    return False


def confirmar_pagamento_manual(cobranca: CobrancaAluguel, *, usuario=None) -> bool:
    """Confirmação feita pelo financeiro (ex.: PIX pago direto na chave da casa).

    Antes confere no Mercado Pago, para registrar o pagamento real se houver;
    depois cancela o PIX pendente no gateway para o morador não pagar duas vezes.
    """
    if cobranca.status == 'pago':
        enviar_comprovante_se_pendente(cobranca)
        return False
    if cobranca.payment_id and mercado_pago_configurado():
        try:
            if verificar_cobranca_no_gateway(cobranca):
                return True
        except Exception:
            logger.exception('Falha ao conferir cobranca no Mercado Pago antes da confirmacao manual.', extra={'cobranca_id': cobranca.id})
        cobranca.refresh_from_db()
        if cobranca.status == 'pago':
            return False
    payment_id_pendente = cobranca.payment_id
    payload = dict(cobranca.provider_payload or {})
    payload['confirmacao_manual'] = {
        'usuario': getattr(usuario, 'username', '') or '',
        'em': timezone.now().isoformat(),
    }
    confirmada = confirmar_pagamento_aluguel(cobranca, status_gateway='confirmado_manual', provider_payload=payload)
    if confirmada and payment_id_pendente:
        cancelar_pagamento_mercado_pago(payment_id_pendente)
    return confirmada


def email_configurado() -> bool:
    """False quando o recibo não tem como sair (SMTP apontando para localhost)."""
    backend = getattr(settings, 'EMAIL_BACKEND', '') or ''
    if not backend.endswith('smtp.EmailBackend'):
        return True
    host = (getattr(settings, 'EMAIL_HOST', '') or '').strip().lower()
    return host not in {'', 'localhost', '127.0.0.1'}


def cobranca_usa_pix_local(cobranca: CobrancaAluguel) -> bool:
    """PIX gerado na chave da casa: o dinheiro não passa pelo Mercado Pago."""
    return cobranca.status != 'pago' and (
        (cobranca.provider_payload or {}).get('modo') == 'local' or not cobranca.payment_id
    )


def avisos_pagamento_aluguel(cobrancas) -> list[str]:
    """Explica na tela do financeiro por que um pagamento não vai se confirmar sozinho."""
    avisos = []
    locais = [c for c in cobrancas if c.txid and cobranca_usa_pix_local(c)]
    if not mercado_pago_configurado():
        avisos.append(
            'Mercado Pago não configurado (MERCADOPAGO_ACCESS_TOKEN): os boletos saem com PIX na chave da casa '
            'e o pagamento precisa ser confirmado manualmente no botão "Confirmar pagamento".'
        )
    elif locais:
        detalhe = next(((c.provider_payload or {}).get('detalhe') for c in locais if (c.provider_payload or {}).get('detalhe')), '')
        motivo = f' Resposta do Mercado Pago: "{detalhe}".' if detalhe else ''
        if 'live credentials' in (detalhe or '').lower():
            motivo += (
                ' Isso acontece quando o token é de um usuário de teste: use o Access Token de produção '
                'da conta real que recebe o aluguel.'
            )
        avisos.append(
            f'{len(locais)} boleto(s) deste mês saíram com PIX na chave da casa porque o Mercado Pago não criou a cobrança.'
            f'{motivo} Esses pagamentos não são reconhecidos sozinhos: confirme no botão "Confirmar pagamento" '
            'ou gere o boleto de novo depois de corrigir o token.'
        )
    if not email_configurado():
        avisos.append(
            'Email não configurado (DJANGO_EMAIL_HOST): o recibo não é enviado ao morador. '
            'O recibo em PDF continua disponível no botão "Gerar boleto de aluguel" do mês pago.'
        )
    return avisos


def verificar_pagamentos_pendentes(cobrancas=None) -> dict[str, int]:
    """Confirma pagamentos que o webhook não avisou e reenvia recibos pendentes."""
    confirmadas = 0
    if mercado_pago_configurado():
        pendentes = cobrancas if cobrancas is not None else CobrancaAluguel.objects.filter(status='aguardando_pagamento')
        for cobranca in pendentes.select_related('morador').exclude(txid=''):
            try:
                if verificar_cobranca_no_gateway(cobranca):
                    confirmadas += 1
            except Exception:
                logger.exception('Falha ao verificar cobranca de aluguel no Mercado Pago.', extra={'cobranca_id': cobranca.id})

    reenviados = 0
    limite = timezone.now() - JANELA_REENVIO_COMPROVANTE
    sem_recibo = CobrancaAluguel.objects.select_related('morador').filter(
        status='pago',
        comprovante_enviado_em__isnull=True,
        pago_em__gte=limite,
    )
    for cobranca in sem_recibo:
        if enviar_comprovante_se_pendente(cobranca):
            reenviados += 1
    return {'confirmadas': confirmadas, 'comprovantes_enviados': reenviados}

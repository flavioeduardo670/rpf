import json
import logging

from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import CobrancaAluguel, Organizacao, PedidoIngressoRock
from core.organizacao_atual import na_organizacao
from core.services.aluguel import confirmar_pagamento_aluguel
from core.services.pix_gateway import consultar_evento_mercado_pago, mercado_pago_configurado, validar_assinatura_webhook
from core.services.rock import confirmar_pagamento_pedido


logger = logging.getLogger(__name__)
STATUS_PAGO = {'pago', 'paid', 'concluido', 'approved', 'accredited'}


def _extrair_identificadores_webhook(request, payload):
    data = payload.get('data') if isinstance(payload.get('data'), dict) else {}
    payment_id = str(
        data.get('id')
        or payload.get('id')
        or payload.get('resource')
        or request.GET.get('data.id')
        or request.GET.get('id')
        or ''
    ).strip()
    txid = str(payload.get('txid') or payload.get('external_reference') or '').strip()
    # Notificações IPN antigas chegam como ?topic=payment&id=123.
    event_type = str(payload.get('type') or payload.get('topic') or request.GET.get('type') or request.GET.get('topic') or '').strip().lower()
    return payment_id, txid, event_type


def _organizacao_do_webhook(slug):
    """O cliente vem no endereço (.../webhook/<slug>/). O endereço antigo, sem
    cliente, é o que os pagamentos criados antes disto usam: é do cliente original
    da instalação (a primeira organização)."""
    ativas = Organizacao.objects.filter(ativa=True)
    if slug:
        return ativas.filter(slug=slug).first()
    return ativas.order_by('id').first()


@csrf_exempt
@require_POST
def webhook_pix(request, organizacao=None):
    org = _organizacao_do_webhook(organizacao)
    if org is None:
        raise Http404('Organização desconhecida.')
    # Assinatura, token do Mercado Pago e consultas: tudo do cliente do endereço.
    with na_organizacao(org):
        return _processar_webhook(request)


def _processar_webhook(request):
    try:
        payload = json.loads(request.body.decode('utf-8') or '{}')
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponseBadRequest('Payload invalido.')

    payment_id, txid, event_type = _extrair_identificadores_webhook(request, payload)
    assinatura = request.headers.get('X-Signature') or request.headers.get('X-Webhook-Signature', '')
    request_id = request.headers.get('X-Request-Id', '')
    # Pelo padrão do Mercado Pago, o manifesto assinado usa o data.id da query
    # string (em minúsculas). Se ele não vier na URL, o campo é omitido do
    # manifesto; usar o id do corpo como fallback invalidava assinaturas legítimas.
    data_id = (request.GET.get('data.id') or '').strip().lower()
    status = (payload.get('status') or '').strip().lower()
    if not validar_assinatura_webhook(request.body, assinatura, request_id=request_id, data_id=data_id):
        # Notificações IPN (?topic=payment&id=...) não vêm assinadas, e um
        # segredo diferente do painel recusava todos os avisos. Sem assinatura
        # válida o corpo não é confiável, mas o id do pagamento pode ser
        # conferido na API com o nosso token: só o que o Mercado Pago responder
        # vale (um id falso ou de outra conta volta 404 e é ignorado).
        if not (payment_id and mercado_pago_configurado() and event_type in {'', 'payment', 'merchant_order'}):
            return HttpResponseBadRequest('Assinatura invalida.')
        logger.info('Webhook PIX sem assinatura valida; conferindo na API do Mercado Pago.', extra={'event': 'pix.webhook.unsigned_checked', 'event_type': event_type, 'payment_id': payment_id})
        txid = ''
        status = ''
        payload = {}

    provider_payload = payload
    if payment_id and (mercado_pago_configurado() or event_type == 'order'):
        resultado = consultar_evento_mercado_pago(payment_id, event_type, payload)
        txid = resultado.get('txid') or txid
        status = resultado.get('status') or status
        provider_payload = resultado.get('provider_payload') or provider_payload
        payment_id = resultado.get('payment_id') or payment_id
        if status in {'nao_encontrado', 'ignorado'} and not txid:
            logger.warning('Webhook PIX Mercado Pago ignorado sem pagamento processavel.', extra={'event': 'pix.webhook.ignored', 'event_type': event_type, 'payment_id': payment_id, 'status': status})
            return JsonResponse({'ok': True, 'detail': status})

    if not txid and not payment_id:
        return HttpResponseBadRequest('Identificador do pagamento obrigatorio.')

    pedido = PedidoIngressoRock.objects.filter(txid=txid).first() if txid else None
    if pedido:
        pedido.status_gateway = status or pedido.status_gateway
        pedido.webhook_recebido_em = timezone.now()
        pedido.save(update_fields=['status_gateway', 'webhook_recebido_em'])

        if status in STATUS_PAGO and pedido.status != 'pago':
            confirmar_pagamento_pedido(pedido)

        return JsonResponse({'ok': True, 'tipo': 'pedido'})

    cobrancas = CobrancaAluguel.objects.select_related('morador')
    cobranca = cobrancas.filter(payment_id=payment_id).first() if payment_id else None
    if not cobranca and txid:
        cobranca = cobrancas.filter(txid=txid).first()
    if not cobranca:
        return JsonResponse({'ok': True, 'detail': 'pagamento_nao_encontrado'})

    cobranca.webhook_recebido_em = timezone.now()
    cobranca.save(update_fields=['webhook_recebido_em', 'atualizado_em'])
    if status in STATUS_PAGO:
        # Idempotente: confirma uma vez e, se o recibo ainda não saiu (falha
        # anterior de email), tenta enviá-lo de novo.
        confirmar_pagamento_aluguel(
            cobranca,
            status_gateway=status,
            provider_payload=provider_payload,
            payment_id=payment_id,
        )
    elif cobranca.status != 'pago':
        cobranca.status_gateway = status or cobranca.status_gateway
        cobranca.provider_payload = provider_payload
        cobranca.save(update_fields=['status_gateway', 'provider_payload', 'atualizado_em'])

    return JsonResponse({'ok': True, 'tipo': 'aluguel'})

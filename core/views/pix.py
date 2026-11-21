import json
import logging

from django.http import HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import CobrancaAluguel, PedidoIngressoRock
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


@csrf_exempt
@require_POST
def webhook_pix(request):
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
    if not validar_assinatura_webhook(request.body, assinatura, request_id=request_id, data_id=data_id):
        return HttpResponseBadRequest('Assinatura invalida.')

    status = (payload.get('status') or '').strip().lower()
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

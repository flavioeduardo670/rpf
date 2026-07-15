import json
import logging

from django.http import HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import CobrancaAluguel, Mensalidade, PedidoIngressoRock
from core.services.pix_gateway import consultar_evento_mercado_pago, validar_assinatura_webhook
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
    event_type = str(payload.get('type') or request.GET.get('type') or '').strip().lower()
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
    data_id = request.GET.get('data.id') or payment_id
    if not validar_assinatura_webhook(request.body, assinatura, request_id=request_id, data_id=data_id):
        return HttpResponseBadRequest('Assinatura invalida.')

    status = (payload.get('status') or '').strip().lower()
    provider_payload = payload
    if payment_id:
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

    cobranca.status_gateway = status or cobranca.status_gateway
    cobranca.webhook_recebido_em = timezone.now()
    cobranca.provider_payload = provider_payload
    if payment_id:
        cobranca.payment_id = payment_id
    update_fields = ['status_gateway', 'webhook_recebido_em', 'provider_payload', 'payment_id', 'atualizado_em']
    enviar_comprovante = False
    if status in STATUS_PAGO and cobranca.status != 'pago':
        cobranca.status = 'pago'
        cobranca.pago_em = timezone.now()
        update_fields.extend(['status', 'pago_em'])
        Mensalidade.objects.update_or_create(
            morador=cobranca.morador,
            mes_referencia=cobranca.mes_referencia,
            defaults={'valor': cobranca.valor, 'pago': True, 'data_pagamento': timezone.localdate(cobranca.pago_em)},
        )
        enviar_comprovante = True
    cobranca.save(update_fields=update_fields)
    if enviar_comprovante:
        from core.views.financeiro import enviar_comprovante_aluguel_por_email
        try:
            enviar_comprovante_aluguel_por_email(cobranca)
        except Exception:
            logger.exception('Falha ao enviar comprovante de aluguel por email.', extra={'cobranca_id': cobranca.id})

    return JsonResponse({'ok': True, 'tipo': 'aluguel'})

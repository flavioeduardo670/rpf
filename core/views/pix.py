import json

from django.http import HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import PedidoIngressoRock
from core.services.pix_gateway import validar_assinatura_webhook
from core.services.rock import confirmar_pagamento_pedido


@csrf_exempt
@require_POST
def webhook_pix(request):
    assinatura = request.headers.get('X-Webhook-Signature', '')
    if not validar_assinatura_webhook(request.body, assinatura):
        return HttpResponseBadRequest('Assinatura invalida.')

    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return HttpResponseBadRequest('Payload invalido.')

    txid = (payload.get('txid') or '').strip()
    status = (payload.get('status') or '').strip().lower()
    if not txid:
        return HttpResponseBadRequest('txid obrigatorio.')

    pedido = PedidoIngressoRock.objects.filter(txid=txid).first()
    if not pedido:
        return JsonResponse({'ok': True, 'detail': 'pedido_nao_encontrado'})

    pedido.status_gateway = status or pedido.status_gateway
    pedido.webhook_recebido_em = timezone.now()
    pedido.save(update_fields=['status_gateway', 'webhook_recebido_em'])

    if status in {'pago', 'paid', 'concluido', 'approved'} and pedido.status != 'pago':
        confirmar_pagamento_pedido(pedido)

    return JsonResponse({'ok': True})

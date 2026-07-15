import json
import logging

from django.http import HttpResponseBadRequest, JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from core.models import CobrancaAluguel, Mensalidade, PedidoIngressoRock
from core.services.pix_gateway import validar_assinatura_webhook
from core.services.rock import confirmar_pagamento_pedido


logger = logging.getLogger(__name__)


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
    if pedido:
        pedido.status_gateway = status or pedido.status_gateway
        pedido.webhook_recebido_em = timezone.now()
        pedido.save(update_fields=['status_gateway', 'webhook_recebido_em'])

        if status in {'pago', 'paid', 'concluido', 'approved'} and pedido.status != 'pago':
            confirmar_pagamento_pedido(pedido)

        return JsonResponse({'ok': True})

    cobranca = CobrancaAluguel.objects.select_related('morador').filter(txid=txid).first()
    if not cobranca:
        return JsonResponse({'ok': True, 'detail': 'pedido_nao_encontrado'})

    cobranca.status_gateway = status or cobranca.status_gateway
    cobranca.webhook_recebido_em = timezone.now()
    cobranca.provider_payload = payload
    update_fields = ['status_gateway', 'webhook_recebido_em', 'provider_payload', 'atualizado_em']
    enviar_comprovante = False
    if status in {'pago', 'paid', 'concluido', 'approved'} and cobranca.status != 'pago':
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

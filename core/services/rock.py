from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from core.models import IngressoRock, LoteIngressoRock, PedidoIngressoRock


def recalcular_quantidade_vendida_por_lote(evento):
    lotes = LoteIngressoRock.objects.filter(rock_evento=evento)
    for lote in lotes:
        total_vendido = (
            IngressoRock.objects.filter(rock_evento=evento, observacao=f'Lote: {lote.nome}')
            .aggregate(total=Sum('quantidade_ingressos'))['total']
            or 0
        )
        if lote.quantidade_vendida != total_vendido:
            lote.quantidade_vendida = total_vendido
            lote.save(update_fields=['quantidade_vendida'])


def recalcular_quantidade_pessoas_evento(evento):
    total_pessoas = (
        IngressoRock.objects.filter(rock_evento=evento).aggregate(total=Sum('quantidade_ingressos'))['total']
        or 0
    )
    if evento.quantidade_pessoas != total_pessoas:
        evento.quantidade_pessoas = total_pessoas
        evento.save(update_fields=['quantidade_pessoas'])
    return total_pessoas


def criar_ingresso_rock(*, evento, lote, nome, telefone, quantidade_ingressos, status_pagamento, observacao=None):
    with transaction.atomic():
        lote = LoteIngressoRock.objects.select_for_update().get(pk=lote.pk)
        disponivel = lote.quantidade_total - lote.quantidade_vendida
        if quantidade_ingressos > disponivel:
            raise PermissionDenied('Quantidade indisponivel para este lote.')

        ingresso = IngressoRock.objects.create(
            rock_evento=evento,
            nome=nome,
            telefone=telefone,
            quantidade_ingressos=quantidade_ingressos,
            valor_unitario=lote.preco,
            status_pagamento=status_pagamento,
            observacao=observacao or f'Lote: {lote.nome}',
        )
        lote.quantidade_vendida = lote.quantidade_vendida + quantidade_ingressos
        lote.save(update_fields=['quantidade_vendida'])
        recalcular_quantidade_pessoas_evento(evento)
        return ingresso


def remover_ingresso_rock(ingresso):
    with transaction.atomic():
        evento = ingresso.rock_evento
        quantidade = ingresso.quantidade_ingressos
        lote = None
        if ingresso.observacao and ingresso.observacao.startswith('Lote: '):
            nome_lote = ingresso.observacao.replace('Lote: ', '', 1)
            lote = LoteIngressoRock.objects.select_for_update().filter(rock_evento=evento, nome=nome_lote).first()

        ingresso.delete()

        if lote:
            lote.quantidade_vendida = max(lote.quantidade_vendida - quantidade, 0)
            lote.save(update_fields=['quantidade_vendida'])
        else:
            recalcular_quantidade_vendida_por_lote(evento)

        recalcular_quantidade_pessoas_evento(evento)


def confirmar_pagamento_pedido(pedido_pagamento):
    with transaction.atomic():
        pedido_pagamento = PedidoIngressoRock.objects.select_for_update().select_related('lote', 'rock_evento').get(
            pk=pedido_pagamento.pk
        )
        lote = LoteIngressoRock.objects.select_for_update().get(pk=pedido_pagamento.lote_id)
        disponivel = lote.quantidade_total - lote.quantidade_vendida
        if pedido_pagamento.quantidade > disponivel:
            raise PermissionDenied('Quantidade indisponivel para este lote.')

        pedido_pagamento.status = 'pago'
        pedido_pagamento.pago_em = timezone.now()
        pedido_pagamento.save(update_fields=['status', 'pago_em'])

        criar_ingresso_rock(
            evento=pedido_pagamento.rock_evento,
            lote=lote,
            nome=pedido_pagamento.nome_comprador,
            telefone=pedido_pagamento.telefone,
            quantidade_ingressos=pedido_pagamento.quantidade,
            status_pagamento='pago',
            observacao=f'Lote: {pedido_pagamento.lote.nome}',
        )

        return pedido_pagamento

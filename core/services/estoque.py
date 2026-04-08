from django.db import transaction

from core.models import ConsumoEstoque, LocalArmazenamento, Morador, Produto, Setor


SETORES_BASE = ['Infraestrutura', 'Hotelaria', 'Rock']
LOCAIS_BASE = [
    'Mala de ferramenta',
    'Garagem',
    'Lavanderia',
    'Cozinha',
    'Sala da cozinha',
    'Sala dos quadrinhos',
    'Terceiro andar',
    'Primeiro andar',
]


def garantir_setores_e_locais_base():
    for nome in SETORES_BASE:
        Setor.objects.get_or_create(nome=nome)
    for nome in LOCAIS_BASE:
        LocalArmazenamento.objects.get_or_create(nome=nome)


def ajustar_estoque_produto(produto_id, quantidade_delta):
    produto = Produto.objects.select_for_update().get(pk=produto_id)
    produto.quantidade += quantidade_delta
    produto.save(update_fields=['quantidade'])
    return produto


def obter_morador_casa():
    return Morador.objects.get_or_create(
        nome='Casa',
        defaults={'apelido': 'Casa', 'ativo': False},
    )[0]


def sincronizar_consumo_item(*, consumo_atual, produto_id, quantidade, morador, data, setor=None, rock_evento=None):
    with transaction.atomic():
        if consumo_atual:
            if consumo_atual.produto_id != produto_id:
                ajustar_estoque_produto(consumo_atual.produto_id, consumo_atual.quantidade)
                ajustar_estoque_produto(produto_id, -quantidade)
            else:
                diff = quantidade - consumo_atual.quantidade
                if diff:
                    ajustar_estoque_produto(produto_id, -diff)

            consumo_atual.produto_id = produto_id
            consumo_atual.morador = morador
            consumo_atual.data = data
            consumo_atual.quantidade = quantidade
            if setor is not None:
                consumo_atual.setor = setor
            if rock_evento is not None:
                consumo_atual.rock_evento = rock_evento
            consumo_atual.save()
            return consumo_atual, False

        ajustar_estoque_produto(produto_id, -quantidade)
        consumo = ConsumoEstoque.objects.create(
            morador=morador,
            produto_id=produto_id,
            quantidade=quantidade,
            data=data,
            setor=setor or 'almoxarifado',
            rock_evento=rock_evento,
        )
        return consumo, True


def remover_consumo_e_devolver_estoque(consumo):
    if not consumo or not consumo.produto_id:
        return
    with transaction.atomic():
        ajustar_estoque_produto(consumo.produto_id, consumo.quantidade)
        consumo.delete()

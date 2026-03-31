from datetime import date
from decimal import Decimal

from django.db.models import Sum
from django.utils import timezone

from core.models import (
    AjusteMorador,
    ConfiguracaoFinanceira,
    ContaFixa,
    DescontoMensal,
    Morador,
    NotaParcela,
    PendenciaMensal,
)


def resolver_mes_referencia(mes_param):
    if mes_param:
        try:
            ano, mes = [int(x) for x in mes_param.split('-')]
            return date(ano, mes, 1)
        except ValueError:
            pass
    return timezone.localdate().replace(day=1)


def calcular_rateio_financeiro(mes_referencia, incluir_pendencia=True):
    parcelas_mes = NotaParcela.objects.filter(
        mes_referencia=mes_referencia,
        nota__setor='compras',
    ).select_related('nota')
    parcelas_consumo = parcelas_mes.filter(nota__tipo_item='Bem de Consumo').exclude(nota__categoria_compra='rock')
    parcelas_material = parcelas_mes.filter(nota__tipo_item='Bem Material').exclude(nota__categoria_compra='rock')
    parcelas_rateio = parcelas_mes.filter(
        nota__tipo_item__in=['Bem de Consumo', 'Bem Material']
    ).exclude(nota__categoria_compra='rock')

    total_caixinha_mes = parcelas_consumo.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_parcelas_material = parcelas_material.aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_parcelas_mes_rateio = (total_caixinha_mes + total_parcelas_material).quantize(Decimal('0.01'))
    total_despesas = parcelas_rateio.filter(status='pago').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_pendente = parcelas_rateio.filter(status='pendente').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    configuracao = ConfiguracaoFinanceira.objects.order_by('-id').first()
    valor_aluguel = configuracao.valor_aluguel if configuracao else Decimal('0.00')
    contas_fixas = list(ContaFixa.objects.filter(ativo=True).order_by('nome'))
    valor_fixas_total = sum((conta.valor for conta in contas_fixas), Decimal('0.00'))

    desconto_obj = DescontoMensal.objects.filter(mes_referencia=mes_referencia).first()
    pendencia_obj = PendenciaMensal.objects.filter(mes_referencia=mes_referencia).first()
    desconto_total_mes = desconto_obj.valor_total if desconto_obj else Decimal('0.00')
    pendencia_total_mes = (
        pendencia_obj.valor_total if pendencia_obj and incluir_pendencia else Decimal('0.00')
    )

    total_rateio = (
        valor_aluguel
        + valor_fixas_total
        + total_parcelas_mes_rateio
        - desconto_total_mes
        + pendencia_total_mes
    )

    moradores_ativos = list(Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome'))
    total_moradores_ativos = len(moradores_ativos)

    def _dividir_total(total):
        if total_moradores_ativos == 0:
            return Decimal('0.00')
        return (total / total_moradores_ativos).quantize(Decimal('0.01'))

    valor_por_morador = _dividir_total(total_rateio)
    valor_variavel_por_morador = _dividir_total(valor_fixas_total)
    parcelas_por_morador = _dividir_total(total_parcelas_material)
    caixinha_por_morador = _dividir_total(total_caixinha_mes)
    desconto_por_morador = _dividir_total(desconto_total_mes)
    pendencia_por_morador = _dividir_total(pendencia_total_mes)

    ajustes_mes = AjusteMorador.objects.filter(mes_referencia=mes_referencia)
    total_peso_ativos = sum((m.peso_quarto or Decimal('0.00')) for m in moradores_ativos) or Decimal('0.00')

    rateio_moradores = []
    for morador in moradores_ativos:
        if total_peso_ativos > 0:
            aluguel_share = (valor_aluguel * (morador.peso_quarto / total_peso_ativos)).quantize(Decimal('0.01'))
        else:
            aluguel_share = _dividir_total(valor_aluguel)

        ajustes_morador = ajustes_mes.filter(morador=morador)
        extra_total = ajustes_morador.filter(tipo='extra').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        desconto_individual = (
            ajustes_morador.filter(tipo='desconto').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        )

        desconto_total = (desconto_por_morador + desconto_individual).quantize(Decimal('0.01'))
        extras_total = (extra_total + pendencia_por_morador).quantize(Decimal('0.01'))
        valor_total = (
            aluguel_share
            + valor_variavel_por_morador
            + caixinha_por_morador
            + parcelas_por_morador
            + pendencia_por_morador
            - desconto_por_morador
            - desconto_individual
            + extra_total
        ).quantize(Decimal('0.01'))

        rateio_moradores.append(
            {
                'morador': morador,
                'aluguel': aluguel_share,
                'fixas': valor_variavel_por_morador,
                'fixas_detalhe': [
                    _dividir_total(conta.valor) if total_moradores_ativos > 0 else Decimal('0.00')
                    for conta in contas_fixas
                ],
                'caixinha': caixinha_por_morador,
                'parcelas': parcelas_por_morador,
                'desconto': desconto_total,
                'extra': extras_total,
                'valor': valor_total,
            }
        )

    return {
        'parcelas_rateio': parcelas_rateio,
        'total_caixinha_mes': total_caixinha_mes,
        'total_parcelas_material': total_parcelas_material,
        'total_parcelas_mes_rateio': total_parcelas_mes_rateio,
        'total_despesas': total_despesas,
        'total_pendente': total_pendente,
        'valor_aluguel': valor_aluguel,
        'contas_fixas': contas_fixas,
        'valor_fixas_total': valor_fixas_total,
        'desconto_total_mes': desconto_total_mes,
        'pendencia_total_mes': pendencia_total_mes,
        'total_rateio': total_rateio,
        'moradores_ativos': moradores_ativos,
        'total_moradores_ativos': total_moradores_ativos,
        'valor_por_morador': valor_por_morador,
        'valor_variavel_por_morador': valor_variavel_por_morador,
        'parcelas_por_morador': parcelas_por_morador,
        'caixinha_por_morador': caixinha_por_morador,
        'desconto_por_morador': desconto_por_morador,
        'pendencia_por_morador': pendencia_por_morador,
        'rateio_moradores': rateio_moradores,
    }


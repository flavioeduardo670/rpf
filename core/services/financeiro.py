from datetime import date, timedelta
from decimal import Decimal
import unicodedata

from django.db.models import Sum
from django.utils import timezone

from core.models import AjusteMorador, ConfiguracaoFinanceira, ContaFixa, Morador, NotaParcela, PendenciaMensalItem


def _normalizar_tipo_item(tipo_item):
    texto = unicodedata.normalize('NFKD', str(tipo_item or '')).encode('ascii', 'ignore').decode('ascii')
    texto = texto.lower().replace('_', ' ').replace('-', ' ').strip()
    texto = ' '.join(texto.split())
    if 'material' in texto:
        return 'material'
    if 'consumo' in texto:
        return 'consumo'
    return 'outro'


def resolver_mes_referencia(mes_param):
    if mes_param:
        try:
            ano, mes = [int(x) for x in mes_param.split('-')]
            return date(ano, mes, 1)
        except ValueError:
            pass
    hoje = timezone.localdate()
    if hoje.day >= 11:
        return (hoje.replace(day=1) + timedelta(days=32)).replace(day=1)
    return hoje.replace(day=1)


def calcular_rateio_financeiro(mes_referencia, incluir_pendencia=True):
    parcelas_mes = NotaParcela.objects.filter(
        mes_referencia=mes_referencia,
        nota__setor='compras',
        nota__cobrar_no_aluguel=True,
    ).select_related('nota').prefetch_related('rateio_exclusoes')
    parcelas_rateio = parcelas_mes.exclude(nota__categoria_compra='rock')
    parcelas_consumo_lista = []
    parcelas_material_lista = []
    for parcela in parcelas_rateio:
        tipo_normalizado = _normalizar_tipo_item(parcela.nota.tipo_item)
        if tipo_normalizado == 'material':
            parcelas_material_lista.append(parcela)
        else:
            parcelas_consumo_lista.append(parcela)

    total_caixinha_mes = sum((parcela.valor for parcela in parcelas_consumo_lista), Decimal('0.00'))
    total_parcelas_material = sum((parcela.valor for parcela in parcelas_material_lista), Decimal('0.00'))
    total_parcelas_mes_rateio = (total_caixinha_mes + total_parcelas_material).quantize(Decimal('0.01'))
    total_despesas = parcelas_rateio.filter(status='pago').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    total_pendente = parcelas_rateio.filter(status='pendente').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')

    configuracao = ConfiguracaoFinanceira.objects.order_by('-id').first()
    valor_aluguel = configuracao.valor_aluguel if configuracao else Decimal('0.00')
    contas_fixas = list(ContaFixa.objects.filter(ativo=True).order_by('nome'))
    valor_fixas_total = sum((conta.valor for conta in contas_fixas), Decimal('0.00'))

    pendencias_items = list(PendenciaMensalItem.objects.filter(mes_referencia=mes_referencia).order_by('id'))
    desconto_itens_total = sum((item.valor for item in pendencias_items if item.tipo == 'desconto'), Decimal('0.00'))
    pendencia_itens_total = sum((item.valor for item in pendencias_items if item.tipo == 'extra'), Decimal('0.00'))
    desconto_total_mes = desconto_itens_total
    pendencia_total_mes = pendencia_itens_total if incluir_pendencia else Decimal('0.00')

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

    caixinha_por_morador_map = {morador.id: Decimal('0.00') for morador in moradores_ativos}
    parcelas_material_por_morador_map = {morador.id: Decimal('0.00') for morador in moradores_ativos}

    def _distribuir_por_inclusao(parcela, acumulador):
        excluidos_ids = {item.morador_id for item in parcela.rateio_exclusoes.all()}
        participantes = [morador.id for morador in moradores_ativos if morador.id not in excluidos_ids]
        if not participantes:
            participantes = [morador.id for morador in moradores_ativos]
            if not participantes:
                return
        valor_total = parcela.valor or Decimal('0.00')
        valor_base = (valor_total / len(participantes)).quantize(Decimal('0.01'))
        restante = valor_total
        for index, morador_id in enumerate(participantes, start=1):
            valor = valor_base if index < len(participantes) else restante.quantize(Decimal('0.01'))
            acumulador[morador_id] += valor
            restante -= valor

    for parcela in parcelas_consumo_lista:
        _distribuir_por_inclusao(parcela, caixinha_por_morador_map)

    for parcela in parcelas_material_lista:
        _distribuir_por_inclusao(parcela, parcelas_material_por_morador_map)

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
        caixinha_morador = caixinha_por_morador_map.get(morador.id, Decimal('0.00')).quantize(Decimal('0.01'))
        parcelas_morador = parcelas_material_por_morador_map.get(morador.id, Decimal('0.00')).quantize(Decimal('0.01'))
        valor_total = (
            aluguel_share
            + valor_variavel_por_morador
            + caixinha_morador
            + parcelas_morador
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
                'caixinha': caixinha_morador,
                'parcelas': parcelas_morador,
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
        'pendencias_items': pendencias_items,
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

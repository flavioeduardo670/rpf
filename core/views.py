from functools import wraps
from decimal import Decimal
from datetime import date, timedelta, datetime
import csv

from django import forms
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Sum, F, ExpressionWrapper, DecimalField, Case, When, OuterRef, Subquery
from django.forms import inlineformset_factory, modelformset_factory
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required

from .forms import (
    ConfiguracaoFinanceiraForm,
    ConsumoForm,
    MaterialUtilizadoForm,
    OrdemServicoForm,
    PerfilFotoForm,
    ProdutoForm,
    RockEventoForm,
    DescontoMensalForm,
    PendenciaMensalForm,
    AjusteMoradorForm,
    ContaFixaForm,
    CadastroForm,
    AcessoMoradorForm,
)
from .models import (
    ConfiguracaoFinanceira,
    ConsumoEstoque,
    MaterialUtilizado,
    Mensalidade,
    Morador,
    LocalArmazenamento,
    NotaParcela,
    NotaFiscal,
    OrdemServico,
    Produto,
    RockEvento,
    Setor,
    DescontoMensal,
    PendenciaMensal,
    AjusteMorador,
    ContaFixa,
)


MaterialFormSet = inlineformset_factory(
    OrdemServico,
    MaterialUtilizado,
    form=MaterialUtilizadoForm,
    extra=1,
    can_delete=True,
)

ContaFixaFormSet = modelformset_factory(
    ContaFixa,
    form=ContaFixaForm,
    extra=1,
    can_delete=True,
)

AcessoMoradorFormSet = modelformset_factory(
    Morador,
    form=AcessoMoradorForm,
    extra=0,
)



def setor_required(group_name=None, morador_attr=None, morador_view_attr=None, morador_edit_attr=None):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            user = request.user

            if user.is_superuser:
                return view_func(request, *args, **kwargs)

            if group_name and user.groups.filter(name=group_name).exists():
                return view_func(request, *args, **kwargs)

            morador = getattr(user, 'morador', None)
            can_view = False
            can_edit = False

            if morador:
                if morador_attr:
                    can_view = getattr(morador, morador_attr, False)
                    can_edit = can_view
                if morador_view_attr:
                    can_view = can_view or getattr(morador, morador_view_attr, False)
                if morador_edit_attr:
                    can_edit = can_edit or getattr(morador, morador_edit_attr, False)

            if request.method in ('GET', 'HEAD', 'OPTIONS'):
                if can_view or can_edit:
                    return view_func(request, *args, **kwargs)
            else:
                if can_edit:
                    return view_func(request, *args, **kwargs)

            raise PermissionDenied('Voce nao tem permissao para acessar este modulo.')

        return _wrapped

    return decorator


def _can_edit(request, attr_name):
    if request.user.is_superuser:
        return True
    morador = getattr(request.user, 'morador', None)
    return bool(morador and getattr(morador, attr_name, False))


@login_required
def home(request):
    return render(request, 'core/home.html')


def cadastro(request):
    if request.user.is_authenticated:
        return redirect('home')

    if request.method == 'POST':
        form = CadastroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('home')
    else:
        form = CadastroForm()

    return render(request, 'core/cadastro.html', {'form': form})


@login_required
def gerenciar_acessos(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Voce nao tem permissao para acessar este modulo.')

    moradores_qs = Morador.objects.order_by('ordem_hierarquia', 'nome')
    if request.method == 'POST':
        formset = AcessoMoradorFormSet(request.POST, queryset=moradores_qs)
        if formset.is_valid():
            formset.save()
            return redirect('gerenciar_acessos')
    else:
        formset = AcessoMoradorFormSet(queryset=moradores_qs)

    return render(request, 'core/gerenciar_acessos.html', {'formset': formset})


@login_required
def perfil(request):
    morador = getattr(request.user, 'morador', None)
    if request.method == 'POST' and morador:
        foto_form = PerfilFotoForm(request.POST, request.FILES, instance=morador)
        if foto_form.is_valid():
            foto_form.save()
            return redirect('perfil')
    else:
        foto_form = PerfilFotoForm(instance=morador)

    return render(
        request,
        'core/perfil.html',
        {
            'usuario': request.user,
            'morador': morador,
            'foto_form': foto_form,
        },
    )


@login_required
def moradores(request):
    moradores_qs = Morador.objects.select_related('user').all().order_by('ordem_hierarquia', 'nome')
    return render(request, 'core/moradores.html', {'moradores': moradores_qs})


@setor_required(
    group_name='Financeiro',
    morador_view_attr='acesso_financeiro_visualizar',
    morador_edit_attr='acesso_financeiro_editar',
)
def financeiro(request):
    can_edit_financeiro = _can_edit(request, 'acesso_financeiro_editar')
    configuracao = ConfiguracaoFinanceira.objects.order_by('-id').first()
    configuracao_form = None
    if request.method == 'POST':
        if 'desconto_submit' in request.POST:
            mes_referencia_str = request.POST.get('mes_referencia')
            if mes_referencia_str:
                mes_referencia = datetime.strptime(mes_referencia_str, '%Y-%m-%d').date().replace(day=1)
                desconto_form = DescontoMensalForm(request.POST)
                if desconto_form.is_valid():
                    DescontoMensal.objects.update_or_create(
                        mes_referencia=mes_referencia,
                        defaults={'valor_total': desconto_form.cleaned_data['valor_total']},
                    )
                    return redirect(f"{redirect('financeiro').url}?mes={mes_referencia.strftime('%Y-%m')}")
        elif 'ajuste_submit' in request.POST:
            ajuste_form = AjusteMoradorForm(request.POST)
            if ajuste_form.is_valid():
                ajuste = ajuste_form.save(commit=False)
                mes_referencia_str = request.POST.get('mes_referencia')
                ajuste.mes_referencia = datetime.strptime(mes_referencia_str, '%Y-%m-%d').date().replace(day=1)
                ajuste.save()
                return redirect(f"{redirect('financeiro').url}?mes={ajuste.mes_referencia.strftime('%Y-%m')}")
        elif 'pendencia_submit' in request.POST:
            mes_referencia_str = request.POST.get('mes_referencia')
            if mes_referencia_str:
                mes_referencia = datetime.strptime(mes_referencia_str, '%Y-%m-%d').date().replace(day=1)
                pendencia_form = PendenciaMensalForm(request.POST)
                if pendencia_form.is_valid():
                    PendenciaMensal.objects.update_or_create(
                        mes_referencia=mes_referencia,
                        defaults={'valor_total': pendencia_form.cleaned_data['valor_total']},
                    )
                    return redirect(f"{redirect('financeiro').url}?mes={mes_referencia.strftime('%Y-%m')}")
        elif 'fixas_submit' in request.POST:
            fixas_formset = ContaFixaFormSet(request.POST, queryset=ContaFixa.objects.all())
            if fixas_formset.is_valid():
                fixas_formset.save()
                mes_ref = request.POST.get('mes_referencia')
                if mes_ref:
                    return redirect(f"{redirect('financeiro').url}?mes={mes_ref[:7]}")
                return redirect('financeiro')
        else:
            configuracao_form = ConfiguracaoFinanceiraForm(request.POST, instance=configuracao)
            if configuracao_form.is_valid():
                configuracao_form.save()
                return redirect('financeiro')
    if configuracao_form is None:
        configuracao_form = ConfiguracaoFinanceiraForm(instance=configuracao)

    total_recebido = (
        Mensalidade.objects.filter(pago=True).aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    )

    total_expr = ExpressionWrapper(
        Case(
            When(quantidade__gt=0, then=F('quantidade') * F('valor')),
            default=F('valor'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    mes_param = request.GET.get('mes')
    if mes_param:
        try:
            ano, mes = [int(x) for x in mes_param.split('-')]
            mes_referencia = date(ano, mes, 1)
        except ValueError:
            mes_referencia = timezone.localdate().replace(day=1)
    else:
        mes_referencia = timezone.localdate().replace(day=1)

    desconto_obj = DescontoMensal.objects.filter(mes_referencia=mes_referencia).first()
    pendencia_obj = PendenciaMensal.objects.filter(mes_referencia=mes_referencia).first()
    desconto_form = DescontoMensalForm(instance=desconto_obj)
    pendencia_form = PendenciaMensalForm(instance=pendencia_obj)
    ajuste_form = AjusteMoradorForm()
    fixas_formset = ContaFixaFormSet(queryset=ContaFixa.objects.all())

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
    total_despesas = (
        parcelas_rateio.filter(status='pago').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    )

    total_pendente = (
        parcelas_rateio.filter(status='pendente').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    )

    valor_aluguel = configuracao.valor_aluguel if configuracao else Decimal('0.00')
    contas_fixas = list(ContaFixa.objects.filter(ativo=True).order_by('nome'))
    valor_fixas_total = sum((conta.valor for conta in contas_fixas), Decimal('0.00'))
    desconto_total_mes = desconto_obj.valor_total if desconto_obj else Decimal('0.00')
    pendencia_total_mes = pendencia_obj.valor_total if pendencia_obj else Decimal('0.00')
    total_rateio = valor_aluguel + valor_fixas_total + total_parcelas_mes_rateio - desconto_total_mes + pendencia_total_mes

    moradores_ativos = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')
    total_moradores_ativos = moradores_ativos.count()
    valor_por_morador = Decimal('0.00')
    if total_moradores_ativos > 0:
        valor_por_morador = (total_rateio / total_moradores_ativos).quantize(Decimal('0.01'))

    valor_variavel = valor_fixas_total
    valor_variavel_por_morador = Decimal('0.00')
    if total_moradores_ativos > 0:
        valor_variavel_por_morador = (valor_variavel / total_moradores_ativos).quantize(Decimal('0.01'))

    parcelas_por_morador = Decimal('0.00')
    caixinha_por_morador = Decimal('0.00')
    if total_moradores_ativos > 0:
        parcelas_por_morador = (total_parcelas_material / total_moradores_ativos).quantize(Decimal('0.01'))
        caixinha_por_morador = (total_caixinha_mes / total_moradores_ativos).quantize(Decimal('0.01'))
    desconto_por_morador = Decimal('0.00')
    pendencia_por_morador = Decimal('0.00')
    if total_moradores_ativos > 0:
        desconto_por_morador = (desconto_total_mes / total_moradores_ativos).quantize(Decimal('0.01'))
        pendencia_por_morador = (pendencia_total_mes / total_moradores_ativos).quantize(Decimal('0.01'))

    ajustes_mes = AjusteMorador.objects.filter(mes_referencia=mes_referencia)

    rateio_moradores = []
    for morador in moradores_ativos:
        if morador.peso_quarto:
            aluguel_share = (valor_aluguel * (morador.peso_quarto / Decimal('100.00'))).quantize(Decimal('0.01'))
        else:
            aluguel_share = Decimal('0.00')
        ajustes_morador = ajustes_mes.filter(morador=morador)
        extra_total = (
            ajustes_morador.filter(tipo='extra').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        )
        desconto_individual = (
            ajustes_morador.filter(tipo='desconto').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        )
        desconto_total = (desconto_por_morador + desconto_individual).quantize(Decimal('0.01'))
        extras_total = (extra_total + pendencia_por_morador).quantize(Decimal('0.01'))
        total_devido = (
            aluguel_share
            + valor_variavel_por_morador
            + caixinha_por_morador
            + parcelas_por_morador
            + pendencia_por_morador
            - desconto_por_morador
            - desconto_individual
            + extra_total
        ).quantize(Decimal('0.01'))
        fixed_shares = []
        for conta in contas_fixas:
            if total_moradores_ativos > 0:
                fixed_shares.append((conta.valor / total_moradores_ativos).quantize(Decimal('0.01')))
            else:
                fixed_shares.append(Decimal('0.00'))
        rateio_moradores.append(
            {
                'morador': morador,
                'aluguel': aluguel_share,
                'fixas': valor_variavel_por_morador,
                'fixas_detalhe': fixed_shares,
                'caixinha': caixinha_por_morador,
                'parcelas': parcelas_por_morador,
                'desconto': desconto_total,
                'extra': extras_total,
                'valor': (
                    aluguel_share
                    + valor_variavel_por_morador
                    + caixinha_por_morador
                    + parcelas_por_morador
                    + pendencia_por_morador
                    - desconto_por_morador
                    - desconto_individual
                    + extra_total
                ).quantize(Decimal('0.01')),
            }
        )

    saldo = total_recebido - total_despesas
    notas = (
        NotaFiscal.objects.filter(
            parcelas__mes_referencia=mes_referencia,
            setor='compras',
        )
        .distinct()
        .annotate(total_valor=total_expr)
        .order_by('-data_vencimento')
    )
    parcelas_abertas = parcelas_rateio.filter(status='pendente').order_by('vencimento', 'id')
    mes_anterior = (mes_referencia - timedelta(days=1)).replace(day=1)
    mes_proximo = (mes_referencia + timedelta(days=32)).replace(day=1)

    context = {
        'total_recebido': total_recebido,
        'total_despesas': total_despesas,
        'total_pendente': total_pendente,
        'saldo': saldo,
        'valor_aluguel': valor_aluguel,
        'valor_fixas_total': valor_fixas_total,
        'total_rateio': total_rateio,
        'total_moradores_ativos': total_moradores_ativos,
        'valor_por_morador': valor_por_morador,
        'rateio_moradores': rateio_moradores,
        'notas': notas,
        'configuracao_form': configuracao_form,
        'parcelas_abertas': parcelas_abertas,
        'mes_referencia': mes_referencia,
        'mes_anterior': mes_anterior,
        'mes_proximo': mes_proximo,
        'desconto_form': desconto_form,
        'pendencia_form': pendencia_form,
        'ajuste_form': ajuste_form,
        'desconto_total_mes': desconto_total_mes,
        'fixas_formset': fixas_formset,
        'contas_fixas': contas_fixas,
        'rateio_colspan': 7 + len(contas_fixas),
        'caixinha_por_morador': caixinha_por_morador,
        'total_caixinha_mes': total_caixinha_mes,
        'pendencia_total_mes': pendencia_total_mes,
        'can_edit_financeiro': can_edit_financeiro,
    }
    return render(request, 'core/financeiro.html', context)


@setor_required(
    group_name='Financeiro',
    morador_view_attr='acesso_financeiro_visualizar',
    morador_edit_attr='acesso_financeiro_editar',
)
def exportar_financeiro_csv(request):
    total_recebido = (
        Mensalidade.objects.filter(pago=True).aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    )
    total_expr = ExpressionWrapper(
        Case(
            When(quantidade__gt=0, then=F('quantidade') * F('valor')),
            default=F('valor'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )

    mes_param = request.GET.get('mes')
    if mes_param:
        try:
            ano, mes = [int(x) for x in mes_param.split('-')]
            mes_referencia = date(ano, mes, 1)
        except ValueError:
            mes_referencia = timezone.localdate().replace(day=1)
    else:
        mes_referencia = timezone.localdate().replace(day=1)

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
    total_despesas = (
        parcelas_rateio.filter(status='pago').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    )
    total_pendente = (
        parcelas_rateio.filter(status='pendente').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    )

    configuracao = ConfiguracaoFinanceira.objects.order_by('-id').first()
    valor_aluguel = configuracao.valor_aluguel if configuracao else Decimal('0.00')
    valor_fixas_total = (
        ContaFixa.objects.filter(ativo=True).aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
    )
    desconto_obj = DescontoMensal.objects.filter(mes_referencia=mes_referencia).first()
    desconto_total_mes = desconto_obj.valor_total if desconto_obj else Decimal('0.00')
    total_rateio = valor_aluguel + valor_fixas_total + total_parcelas_mes_rateio - desconto_total_mes

    moradores_ativos = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')
    total_moradores_ativos = moradores_ativos.count()
    valor_por_morador = Decimal('0.00')
    if total_moradores_ativos > 0:
        valor_por_morador = (total_rateio / total_moradores_ativos).quantize(Decimal('0.01'))

    valor_variavel = valor_fixas_total
    valor_variavel_por_morador = Decimal('0.00')
    if total_moradores_ativos > 0:
        valor_variavel_por_morador = (valor_variavel / total_moradores_ativos).quantize(Decimal('0.01'))

    notas = (
        NotaFiscal.objects.filter(
            parcelas__mes_referencia=mes_referencia,
            setor='compras',
        )
        .distinct()
        .annotate(total_valor=total_expr)
        .order_by('-data_vencimento')
    )
    saldo = total_recebido - total_despesas

    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="financeiro_{timestamp}.csv"'

    # BOM para abrir acentos corretamente no Excel.
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')

    writer.writerow(['Resumo Financeiro'])
    writer.writerow(['Mes de Referencia', mes_referencia.strftime('%m/%Y')])
    writer.writerow(['Valor do Aluguel', valor_aluguel])
    writer.writerow(['Contas fixas', valor_fixas_total])
    writer.writerow(['Total Recebido', total_recebido])
    writer.writerow(['Despesas Pagas', total_despesas])
    writer.writerow(['Despesas Pendentes', total_pendente])
    writer.writerow(['Saldo Atual', saldo])
    writer.writerow(['Total para Rateio', total_rateio])
    writer.writerow(['Moradores Ativos', total_moradores_ativos])
    writer.writerow(['Valor por Morador', valor_por_morador])
    writer.writerow([])

    writer.writerow(['Aluguel do Mes'])
    writer.writerow(['Morador', 'Aluguel', 'Contas fixas', 'Caixinha', 'Parcelas', 'Desconto', 'Total'])
    for morador in moradores_ativos:
        if morador.peso_quarto:
            aluguel_share = (valor_aluguel * (morador.peso_quarto / Decimal('100.00'))).quantize(Decimal('0.01'))
        else:
            aluguel_share = Decimal('0.00')
        parcelas_por_morador = Decimal('0.00')
        caixinha_por_morador = Decimal('0.00')
        if total_moradores_ativos > 0:
            parcelas_por_morador = (total_parcelas_material / total_moradores_ativos).quantize(Decimal('0.01'))
            caixinha_por_morador = (total_caixinha_mes / total_moradores_ativos).quantize(Decimal('0.01'))
        desconto_por_morador = Decimal('0.00')
        if total_moradores_ativos > 0:
            desconto_por_morador = (desconto_total_mes / total_moradores_ativos).quantize(Decimal('0.01'))
        ajustes_morador = AjusteMorador.objects.filter(morador=morador, mes_referencia=mes_referencia)
        extra_total = (
            ajustes_morador.filter(tipo='extra').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        )
        desconto_individual = (
            ajustes_morador.filter(tipo='desconto').aggregate(total=Sum('valor'))['total'] or Decimal('0.00')
        )
        desconto_final = (desconto_por_morador + desconto_individual - extra_total).quantize(Decimal('0.01'))
        valor_devido = (
            aluguel_share
            + valor_variavel_por_morador
            + parcelas_por_morador
            - desconto_por_morador
            - desconto_individual
            + extra_total
        ).quantize(Decimal('0.01'))
        writer.writerow(
            [
                morador.apelido or morador.nome,
                aluguel_share,
                valor_variavel_por_morador,
                caixinha_por_morador,
                parcelas_por_morador,
                desconto_final,
                (
                    aluguel_share
                    + valor_variavel_por_morador
                    + caixinha_por_morador
                    + parcelas_por_morador
                    - desconto_por_morador
                    - desconto_individual
                    + extra_total
                ).quantize(Decimal('0.01')),
            ]
        )
    writer.writerow([])

    writer.writerow(['Cronograma de Parcelas'])
    writer.writerow(['Descricao', 'Fornecedor', 'Parcela', 'Valor', 'Vencimento', 'Status'])
    for parcela in parcelas_rateio.order_by('vencimento', 'id'):
        writer.writerow(
            [
                parcela.nota.descricao,
                parcela.nota.fornecedor,
                parcela.numero,
                parcela.valor,
                parcela.vencimento,
                parcela.get_status_display(),
            ]
        )

    return response


@require_POST
@setor_required(
    group_name='Financeiro',
    morador_edit_attr='acesso_financeiro_editar',
)
def pagar_nota(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id)
    if nota.status != 'pago':
        nota.status = 'pago'
        nota.data_pagamento = timezone.now().date()
        nota.save(update_fields=['status', 'data_pagamento'])
    return redirect('financeiro')


@require_POST
@setor_required(
    group_name='Financeiro',
    morador_edit_attr='acesso_financeiro_editar',
)
def pagar_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela, id=parcela_id)
    if parcela.status != 'pago':
        parcela.status = 'pago'
        parcela.save(update_fields=['status'])
    return redirect('financeiro')


@setor_required(
    group_name='Financeiro',
    morador_edit_attr='acesso_financeiro_editar',
)
def editar_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela, id=parcela_id)
    if request.method == 'POST':
        form = ParcelaForm(request.POST, instance=parcela)
        if form.is_valid():
            form.save()
            return redirect('financeiro')
    else:
        form = ParcelaForm(instance=parcela)

    return render(request, 'core/editar_parcela.html', {'form': form, 'parcela': parcela})


class NotaFiscalForm(forms.ModelForm):
    class Meta:
        model = NotaFiscal
        fields = [
            'descricao',
            'fornecedor',
            'setor_estoque',
            'local_estoque',
            'tipo_item',
            'quantidade',
            'qualidade',
            'parcelado',
            'quantidade_parcelas',
            'valor',
            'data_emissao',
            'data_vencimento',
            'observacao',
        ]
        labels = {
            'descricao': 'Item',
            'valor': 'Valor unitario',
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setor_nomes = ['Infraestrutura', 'Hotelaria', 'Rock']
        local_nomes = [
            'Mala de ferramenta',
            'Garagem',
            'Lavanderia',
            'Cozinha',
            'Sala da cozinha',
            'Sala dos quadrinhos',
            'Terceiro andar',
            'Primeiro andar',
        ]

        setores = list(Setor.objects.filter(nome__in=setor_nomes))
        setor_map = {s.nome: s for s in setores}
        self.fields['setor_estoque'].choices = [
            (setor_map[nome].id, setor_map[nome].nome)
            for nome in setor_nomes
            if nome in setor_map
        ]
        self.fields['setor_estoque'].required = True

        locais = list(LocalArmazenamento.objects.filter(nome__in=local_nomes))
        local_map = {l.nome: l for l in locais}
        self.fields['local_estoque'].choices = [
            (local_map[nome].id, local_map[nome].nome)
            for nome in local_nomes
            if nome in local_map
        ]
        self.fields['local_estoque'].required = True

        self.fields['tipo_item'] = forms.ChoiceField(
            choices=[
                ('', '---'),
                ('Bem de Uso', 'Bem de Uso'),
                ('Bem Material', 'Bem Material'),
                ('Bem de Consumo', 'Bem de Consumo'),
                ('Bem de Troca', 'Bem de Troca'),
            ],
            required=True,
        )
        self.fields['quantidade_parcelas'].min_value = 1
        self.fields['quantidade_parcelas'].label = 'Quantidade de parcelas'


class ParcelaForm(forms.ModelForm):
    class Meta:
        model = NotaParcela
        fields = ['valor', 'vencimento', 'mes_referencia', 'status']
        widgets = {
            'vencimento': forms.DateInput(attrs={'type': 'date'}),
            'mes_referencia': forms.DateInput(attrs={'type': 'date'}),
        }


@setor_required(
    group_name='Compras',
    morador_view_attr='acesso_compras_visualizar',
    morador_edit_attr='acesso_compras_editar',
)
def compras(request):
    can_edit_compras = _can_edit(request, 'acesso_compras_editar')
    setores_base = ['Infraestrutura', 'Hotelaria', 'Rock']
    locais_base = [
        'Mala de ferramenta',
        'Garagem',
        'Lavanderia',
        'Cozinha',
        'Sala da cozinha',
        'Sala dos quadrinhos',
        'Terceiro andar',
        'Primeiro andar',
    ]

    for nome in setores_base:
        Setor.objects.get_or_create(nome=nome)
    for nome in locais_base:
        LocalArmazenamento.objects.get_or_create(nome=nome)

    if request.method == 'POST':
        form = NotaFiscalForm(request.POST)
        if form.is_valid():
            nota = form.save(commit=False)
            nota.setor = 'compras'
            if not nota.parcelado:
                nota.quantidade_parcelas = 1
            nota.save()
            if nota.quantidade > 0:
                produto, criado = Produto.objects.get_or_create(
                    nome=nota.descricao,
                    setor=nota.setor_estoque,
                    local=nota.local_estoque,
                    defaults={
                        'descricao': nota.tipo_item or '',
                        'quantidade': nota.quantidade,
                        'estoque_minimo': 0,
                    },
                )
                if not criado:
                    produto.quantidade += nota.quantidade
                    if nota.tipo_item and produto.descricao != nota.tipo_item:
                        produto.descricao = nota.tipo_item
                    produto.save(update_fields=['quantidade', 'descricao'])
            criar_parcelas_nota(nota)
            return redirect('compras')
    else:
        form = NotaFiscalForm()

    mes_cobranca_sub = NotaParcela.objects.filter(
        nota_id=OuterRef('pk')
    ).order_by('mes_referencia').values('mes_referencia')[:1]

    notas = NotaFiscal.objects.filter(setor='compras').annotate(
        total_valor=ExpressionWrapper(
            F('quantidade') * F('valor'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        mes_cobranca=Subquery(mes_cobranca_sub),
    ).order_by('-data_emissao')
    return render(
        request,
        'core/compras.html',
        {
            'form': form,
            'notas': notas,
            'can_edit_compras': can_edit_compras,
        },
    )


def _primeiro_vencimento(data_emissao):
    if data_emissao.day >= 5:
        mes = (data_emissao.replace(day=1) + timedelta(days=32)).replace(day=1)
    else:
        mes = data_emissao.replace(day=1)
    return mes.replace(day=5), mes


def criar_parcelas_nota(nota):
    if nota.parcelas.exists():
        return

    quantidade = nota.quantidade_parcelas or 1
    total = (nota.valor or Decimal('0.00')) * (nota.quantidade or 0)
    if quantidade <= 0:
        quantidade = 1

    vencimento, mes_ref = _primeiro_vencimento(nota.data_emissao)
    valor_parcela = (total / quantidade).quantize(Decimal('0.01')) if quantidade else total
    restante = total

    for idx in range(1, quantidade + 1):
        valor = valor_parcela if idx < quantidade else restante.quantize(Decimal('0.01'))
        NotaParcela.objects.create(
            nota=nota,
            numero=idx,
            valor=valor,
            vencimento=vencimento,
            mes_referencia=mes_ref,
            status='pendente',
        )
        restante -= valor
        # proximo mes
        mes_ref = (mes_ref + timedelta(days=32)).replace(day=1)
        vencimento = mes_ref.replace(day=5)


@setor_required(
    group_name='Compras',
    morador_view_attr='acesso_compras_visualizar',
)
def exportar_compras_csv(request):
    notas = NotaFiscal.objects.filter(setor='compras').annotate(
        total_valor=ExpressionWrapper(
            F('quantidade') * F('valor'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        )
    ).order_by('-data_emissao', '-id')
    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="compras_{timestamp}.csv"'

    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Notas de Compras'])
    writer.writerow([
        'Item',
        'Fornecedor',
        'Categoria',
        'Setor',
        'Local',
        'Tipo',
        'Quantidade',
        'Qualidade',
        'Parcelado',
        'Valor unitario',
        'Total',
        'Emissao',
        'Vencimento',
        'Status',
        'Pagamento',
    ])

    for nota in notas:
        writer.writerow(
            [
                nota.descricao,
                nota.fornecedor,
                nota.categoria_compra or 'geral',
                nota.setor_estoque.nome if nota.setor_estoque else '-',
                nota.local_estoque.nome if nota.local_estoque else '-',
                nota.tipo_item or '-',
                nota.quantidade,
                nota.qualidade or '-',
                'Sim' if nota.parcelado else 'Nao',
                nota.valor,
                nota.total_valor,
                nota.data_emissao,
                nota.data_vencimento,
                nota.get_status_display(),
                nota.data_pagamento or '-',
            ]
        )

    return response


@setor_required(
    group_name='Compras',
    morador_edit_attr='acesso_compras_editar',
)
def editar_nota_compra(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id, setor='compras')
    if request.method == 'POST' and 'excluir_submit' in request.POST:
        nota.delete()
        return redirect('compras')

    if request.method == 'POST':
        form = NotaFiscalForm(request.POST, instance=nota)
        if form.is_valid():
            nota_atualizada = form.save(commit=False)
            nota_atualizada.setor = 'compras'
            nota_atualizada.save()
            return redirect('compras')
    else:
        form = NotaFiscalForm(instance=nota)

    return render(request, 'core/editar_nota.html', {'form': form, 'nota': nota})


@setor_required(
    group_name='Rock',
    morador_view_attr='acesso_rock_visualizar',
    morador_edit_attr='acesso_rock_editar',
)
def rock(request):
    can_edit_rock = _can_edit(request, 'acesso_rock_editar')
    if request.method == 'POST':
        evento_form = RockEventoForm(request.POST)
        if evento_form.is_valid():
            evento = evento_form.save()
            return redirect('rock')
    else:
        evento_form = RockEventoForm()

    eventos = RockEvento.objects.order_by('-data')
    consumos_rock = (
        ConsumoEstoque.objects.filter(setor='rock', rock_evento__isnull=False)
        .select_related('rock_evento', 'produto')
        .order_by('-data', '-id')
    )
    return render(
        request,
        'core/rock.html',
        {
            'evento_form': evento_form,
            'eventos': eventos,
            'consumos_rock': consumos_rock,
            'can_edit_rock': can_edit_rock,
        },
    )


@setor_required(
    group_name='Estoque',
    morador_view_attr='acesso_estoque_visualizar',
    morador_edit_attr='acesso_estoque_editar',
)
def almoxarifado(request):
    can_edit_estoque = _can_edit(request, 'acesso_estoque_editar')
    setores_base = ['Infraestrutura', 'Hotelaria', 'Rock']
    locais_base = [
        'Mala de ferramenta',
        'Garagem',
        'Lavanderia',
        'Cozinha',
        'Sala da cozinha',
        'Sala dos quadrinhos',
        'Terceiro andar',
        'Primeiro andar',
    ]

    for nome in setores_base:
        Setor.objects.get_or_create(nome=nome)
    for nome in locais_base:
        LocalArmazenamento.objects.get_or_create(nome=nome)

    produtos = Produto.objects.select_related('setor', 'local').all()
    produto_form = ProdutoForm()

    if request.method == 'POST' and 'produto_submit' in request.POST:
        produto_form = ProdutoForm(request.POST)
        if produto_form.is_valid():
            produto_form.save()
            return redirect('almoxarifado')

    context = {
        'produtos': produtos,
        'produto_form': produto_form,
        'can_edit_estoque': can_edit_estoque,
    }
    return render(request, 'core/almoxarifado.html', context)


@setor_required(
    group_name='Estoque',
    morador_edit_attr='acesso_estoque_editar',
)
def editar_produto(request, produto_id):
    produto = get_object_or_404(Produto, id=produto_id)
    if request.method == 'POST' and 'excluir_submit' in request.POST:
        produto.delete()
        return redirect('almoxarifado')

    if request.method == 'POST':
        form = ProdutoForm(request.POST, instance=produto)
        if form.is_valid():
            form.save()
            return redirect('almoxarifado')
    else:
        form = ProdutoForm(instance=produto)

    return render(request, 'core/editar_produto.html', {'form': form, 'produto': produto})


@setor_required(
    group_name='Estoque',
    morador_edit_attr='acesso_estoque_editar',
)
def registrar_consumo(request):
    if request.method == 'POST':
        form = ConsumoForm(request.POST)
        if form.is_valid():
            consumo = form.save(commit=False)
            with transaction.atomic():
                produto = Produto.objects.select_for_update().get(pk=consumo.produto_id)
                if consumo.quantidade > produto.quantidade:
                    form.add_error(
                        'quantidade',
                        f'Estoque insuficiente para {produto.nome}. Disponivel: {produto.quantidade}.',
                    )
                else:
                    produto.quantidade -= consumo.quantidade
                    produto.save(update_fields=['quantidade'])
                    consumo.produto = produto
                    consumo.save()
                    return redirect('consumo_historico')
    else:
        form = ConsumoForm(initial={'data': timezone.localdate()})

    return render(request, 'core/registrar_consumo.html', {'form': form})


@setor_required(
    group_name='Estoque',
    morador_view_attr='acesso_estoque_visualizar',
)
def consumo_historico(request):
    consumos = ConsumoEstoque.objects.select_related('morador', 'produto').order_by('-data', '-id')
    return render(request, 'core/consumo_historico.html', {'consumos': consumos})


@setor_required(
    group_name='Estoque',
    morador_view_attr='acesso_estoque_visualizar',
)
def exportar_consumo_csv(request):
    consumos = ConsumoEstoque.objects.select_related('morador', 'produto').order_by('-data', '-id')
    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="consumo_{timestamp}.csv"'

    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Historico de Consumo'])
    writer.writerow(['Responsavel', 'Data', 'Item', 'Quantidade'])

    for consumo in consumos:
        writer.writerow(
            [
                consumo.morador.apelido or consumo.morador.nome,
                consumo.data.strftime('%d/%m/%Y'),
                consumo.produto.nome,
                consumo.quantidade,
            ]
        )

    return response


@setor_required(
    group_name='Estoque',
    morador_view_attr='acesso_estoque_visualizar',
)
def exportar_estoque_csv(request):
    produtos = Produto.objects.select_related('setor', 'local').order_by('nome')
    timestamp = timezone.localtime().strftime('%Y%m%d_%H%M%S')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="estoque_{timestamp}.csv"'

    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Estoque do Almoxarifado'])
    writer.writerow(
        [
            'Nome',
            'Tipo',
            'Setor',
            'Local',
            'Quantidade',
            'Estoque minimo',
            'Data de cadastro',
        ]
    )

    for produto in produtos:
        writer.writerow(
            [
                produto.nome,
                produto.descricao or '-',
                produto.setor.nome,
                produto.local.nome if produto.local else '-',
                produto.quantidade,
                produto.estoque_minimo,
                timezone.localtime(produto.data_cadastro).strftime('%d/%m/%Y %H:%M'),
            ]
        )

    return response


@setor_required(
    group_name='Manutencao',
    morador_view_attr='acesso_manutencao_visualizar',
    morador_edit_attr='acesso_manutencao_editar',
)
def manutencao(request):
    can_edit_manutencao = _can_edit(request, 'acesso_manutencao_editar')
    if request.method == 'POST':
        os_form = OrdemServicoForm(request.POST)
        if os_form.is_valid():
            os_form.save()
            return redirect('manutencao')
        else:
            pass
    else:
        os_form = OrdemServicoForm()

    context = {
        'os_form': os_form,
        'ordens': OrdemServico.objects.all().order_by('-numero'),
        'can_edit_manutencao': can_edit_manutencao,
    }
    return render(request, 'core/manutencao.html', context)


@setor_required(
    group_name='Manutencao',
    morador_view_attr='acesso_manutencao_visualizar',
)
def lista_os(request):
    ordens = OrdemServico.objects.all().order_by('-numero')
    return render(request, 'core/lista_os.html', {'ordens': ordens})


@setor_required(
    group_name='Manutencao',
    morador_edit_attr='acesso_manutencao_editar',
)
def editar_os(request, numero):
    os_obj = get_object_or_404(OrdemServico, numero=numero)

    if request.method == 'POST':
        if 'excluir_os' in request.POST:
            with transaction.atomic():
                for material in os_obj.materiais.select_related('consumo'):
                    consumo = getattr(material, 'consumo', None)
                    if consumo:
                        produto = Produto.objects.select_for_update().get(pk=consumo.produto_id)
                        produto.quantidade += consumo.quantidade
                        produto.save(update_fields=['quantidade'])
                        consumo.delete()
                if os_obj.despesa_gerada:
                    NotaFiscal.objects.filter(
                        setor='manutencao',
                        descricao=f"Manutenção OS #{os_obj.numero}",
                    ).delete()
            os_obj.delete()
            return redirect('manutencao')

        os_form = OrdemServicoForm(request.POST, instance=os_obj)
        if os_form.is_valid():
            with transaction.atomic():
                os_salva = os_form.save()

                if os_salva.status == 'finalizada' and not os_salva.despesa_gerada:
                    os_salva.gerar_despesa()

            return redirect('manutencao')
    else:
        os_form = OrdemServicoForm(instance=os_obj)

    return render(
        request,
        'core/editar_os.html',
        {'os_form': os_form, 'os': os_obj},
    )


def processar_consumo_formset(formset):
    deleted_forms = getattr(formset, 'deleted_forms', [])
    for form in deleted_forms:
        obj = getattr(form, 'instance', None)
        if not obj or not obj.pk:
            continue
        consumo = getattr(obj, 'consumo', None)
        if consumo:
            produto = Produto.objects.select_for_update().get(pk=consumo.produto_id)
            produto.quantidade += consumo.quantidade
            produto.save(update_fields=['quantidade'])
            consumo.delete()
        obj.delete()

    for form in formset:
        if not form.cleaned_data or form.cleaned_data.get('DELETE'):
            continue
        material = form.save(commit=False)
        if not material.ordem_servico_id:
            material.ordem_servico = formset.instance
        produto = form.cleaned_data.get('produto')
        morador = form.cleaned_data.get('morador')
        data_consumo = form.cleaned_data.get('data_consumo')
        aplicar_consumo_material(material, produto, morador, data_consumo)


def aplicar_consumo_material(material, produto, morador, data_consumo):
    if material.consumo_id:
        consumo = material.consumo
        if consumo.produto_id != produto.id:
            produto_antigo = Produto.objects.select_for_update().get(pk=consumo.produto_id)
            produto_antigo.quantidade += consumo.quantidade
            produto_antigo.save(update_fields=['quantidade'])

            produto_novo = Produto.objects.select_for_update().get(pk=produto.id)
            produto_novo.quantidade -= material.quantidade
            produto_novo.save(update_fields=['quantidade'])
        else:
            diff = material.quantidade - consumo.quantidade
            if diff != 0:
                produto_atual = Produto.objects.select_for_update().get(pk=produto.id)
                produto_atual.quantidade -= diff
                produto_atual.save(update_fields=['quantidade'])

        consumo.produto = produto
        consumo.morador = morador
        consumo.data = data_consumo
        consumo.quantidade = material.quantidade
        consumo.save(update_fields=['produto', 'morador', 'data', 'quantidade'])
    else:
        produto_atual = Produto.objects.select_for_update().get(pk=produto.id)
        produto_atual.quantidade -= material.quantidade
        produto_atual.save(update_fields=['quantidade'])
        consumo = ConsumoEstoque.objects.create(
            morador=morador,
            produto=produto_atual,
            quantidade=material.quantidade,
            data=data_consumo,
        )
        material.consumo = consumo

    material.produto = produto
    material.morador = morador
    material.data_consumo = data_consumo
    material.nome_material = produto.nome
    material.save()

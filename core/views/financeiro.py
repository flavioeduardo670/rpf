import csv
from datetime import datetime, timedelta
from decimal import Decimal

from django import forms
from django.db.models import Case, DecimalField, ExpressionWrapper, F, OuterRef, Subquery, Sum, When
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.forms import (
    AjusteMoradorForm,
    ConfiguracaoFinanceiraForm,
    ContaFixaForm,
    DescontoMensalForm,
    PendenciaMensalItemForm,
    apply_form_config,
    get_choice_options,
)
from core.models import (
    AjusteMorador,
    Comodo,
    ComprovantePagamentoMorador,
    ConfiguracaoFinanceira,
    ContaFixa,
    LocalArmazenamento,
    Mensalidade,
    Morador,
    NotaFiscal,
    NotaParcela,
    ParcelaRateioExclusao,
    PendenciaMensalItem,
    Produto,
    RockEvento,
    Setor,
)
from core.services.estoque import garantir_setores_e_locais_base
from core.services.financeiro import calcular_rateio_financeiro, resolver_mes_referencia

from .common import can_edit, setor_required


ContaFixaFormSet = forms.modelformset_factory(ContaFixa, form=ContaFixaForm, extra=1, can_delete=True)
AjusteMoradorFormSet = forms.modelformset_factory(AjusteMorador, form=AjusteMoradorForm, extra=1, can_delete=True)
PendenciaMensalItemFormSet = forms.modelformset_factory(PendenciaMensalItem, form=PendenciaMensalItemForm, extra=1, can_delete=True)


class ParcelaForm(forms.ModelForm):
    class Meta:
        model = NotaParcela
        fields = ['valor', 'vencimento', 'mes_referencia', 'status']
        widgets = {
            'vencimento': forms.DateInput(attrs={'type': 'date'}),
            'mes_referencia': forms.DateInput(attrs={'type': 'date'}),
        }


class NotaFiscalForm(forms.ModelForm):
    comodo_estoque = forms.ModelChoiceField(queryset=Comodo.objects.none(), required=False, label='Cômodo')
    rock_evento = forms.ModelChoiceField(queryset=RockEvento.objects.none(), required=False, label='Rock', empty_label='Geral')

    class Meta:
        model = NotaFiscal
        fields = [
            'descricao', 'fornecedor', 'categoria_compra', 'setor_estoque', 'comodo_estoque', 'local_estoque', 'rock_evento',
            'tipo_item', 'quantidade', 'qualidade', 'adicionar_estoque', 'cobrar_no_aluguel', 'parcelado', 'quantidade_parcelas',
            'valor', 'data_emissao', 'data_vencimento', 'status', 'data_pagamento', 'forma_pagamento', 'observacao',
        ]
        labels = {'descricao': 'Item', 'valor': 'Valor unitario'}
        widgets = {k: forms.DateInput(attrs={'type': 'date'}) for k in ['data_emissao', 'data_vencimento', 'data_pagamento']}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setores = {s.nome: s for s in Setor.objects.filter(nome__in=['Infraestrutura', 'Hotelaria', 'Rock'])}
        self.fields['setor_estoque'].choices = [(setores[n].id, setores[n].nome) for n in ['Infraestrutura', 'Hotelaria', 'Rock'] if n in setores]
        self.fields['setor_estoque'].required = False
        self.fields['comodo_estoque'].queryset = Comodo.objects.select_related('andar').order_by('andar__nome', 'nome')
        selected_comodo = None
        if self.data and self.data.get(self.add_prefix('comodo_estoque')):
            selected_comodo = Comodo.objects.filter(pk=self.data.get(self.add_prefix('comodo_estoque'))).first()
        elif self.instance and self.instance.pk and self.instance.local_estoque and self.instance.local_estoque.comodo_id:
            selected_comodo = self.instance.local_estoque.comodo
        self.fields['local_estoque'].queryset = LocalArmazenamento.objects.filter(comodo=selected_comodo).order_by('nome') if selected_comodo else LocalArmazenamento.objects.none()
        self.fields['local_estoque'].required = False
        self.fields['rock_evento'].queryset = RockEvento.objects.order_by('-data', 'nome')
        self.fields['tipo_item'] = forms.ChoiceField(choices=get_choice_options('nota_tipo_item', [('', '---'), ('Bem de Uso', 'Bem de Uso'), ('Bem Material', 'Bem Material'), ('Bem de Consumo', 'Bem de Consumo'), ('Bem de Troca', 'Bem de Troca')]), required=True)
        self.fields['categoria_compra'].choices = get_choice_options('categoria_compra', [('geral', 'Geral'), ('rock', 'Rock')])
        self.fields['quantidade_parcelas'].min_value = 1
        self.fields['quantidade_parcelas'].label = 'Quantidade de parcelas'
        adicionar = self._get_adicionar_estoque_value()
        self.fields['setor_estoque'].required = adicionar
        self.fields['comodo_estoque'].required = adicionar
        self.fields['local_estoque'].required = adicionar
        self.fields['quantidade'].required = adicionar
        apply_form_config(self, 'nota_fiscal_form')

    def clean(self):
        cleaned = super().clean()
        if cleaned.get('categoria_compra') != 'rock':
            cleaned['rock_evento'] = None
        return cleaned

    def _get_adicionar_estoque_value(self):
        if self.data:
            val = self.data.get(self.add_prefix('adicionar_estoque'))
            if val is not None:
                return val in ('on', 'true', 'True', '1')
        if self.instance and self.instance.pk:
            return bool(self.instance.adicionar_estoque)
        return True


@setor_required(group_name='Financeiro', morador_view_attr='acesso_financeiro_visualizar', morador_edit_attr='acesso_financeiro_editar')
def financeiro(request):
    can_edit_financeiro = can_edit(request, 'acesso_financeiro_editar')
    configuracao = ConfiguracaoFinanceira.objects.order_by('-id').first()
    configuracao_form = None
    if request.method == 'POST':
        if 'desconto_submit' in request.POST:
            mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
            form = DescontoMensalForm(request.POST)
            if form.is_valid():
                from core.models import DescontoMensal
                DescontoMensal.objects.update_or_create(mes_referencia=mes, defaults={'valor_total': form.cleaned_data['valor_total']})
                return redirect(f"{redirect('financeiro').url}?mes={mes.strftime('%Y-%m')}")
        elif 'ajuste_submit' in request.POST:
            fs = AjusteMoradorFormSet(
                request.POST,
                queryset=AjusteMorador.objects.filter(mes_referencia=datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)),
                prefix='ajuste',
            )
            if fs.is_valid():
                mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
                for ajuste in fs.save(commit=False):
                    ajuste.mes_referencia = mes
                    ajuste.save()
                for obj in fs.deleted_objects:
                    obj.delete()
                return redirect(f"{redirect('financeiro').url}?mes={mes.strftime('%Y-%m')}")
        elif 'pendencia_submit' in request.POST:
            mes = datetime.strptime(request.POST.get('mes_referencia'), '%Y-%m-%d').date().replace(day=1)
            fs = PendenciaMensalItemFormSet(
                request.POST,
                queryset=PendenciaMensalItem.objects.filter(mes_referencia=mes),
                prefix='pendencia',
            )
            if fs.is_valid():
                itens = fs.save(commit=False)
                for item in itens:
                    item.mes_referencia = mes
                    item.save()
                for obj in fs.deleted_objects:
                    obj.delete()
                return redirect(f"{redirect('financeiro').url}?mes={mes.strftime('%Y-%m')}")
        elif 'fixas_submit' in request.POST:
            fs = ContaFixaFormSet(request.POST, queryset=ContaFixa.objects.all())
            if fs.is_valid():
                fs.save()
                mes_ref = request.POST.get('mes_referencia')
                return redirect(f"{redirect('financeiro').url}?mes={mes_ref[:7]}") if mes_ref else redirect('financeiro')
        else:
            configuracao_form = ConfiguracaoFinanceiraForm(request.POST, instance=configuracao)
            if configuracao_form.is_valid():
                configuracao_form.save()
                return redirect('financeiro')
    if configuracao_form is None:
        configuracao_form = ConfiguracaoFinanceiraForm(instance=configuracao)

    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    resumo = calcular_rateio_financeiro(mes_referencia, incluir_pendencia=True)
    comprovantes_map = {
        item.morador_id: item
        for item in ComprovantePagamentoMorador.objects.filter(
            mes_referencia=mes_referencia,
            morador__in=resumo['moradores_ativos'],
        ).select_related('morador')
    }
    for item in resumo['rateio_moradores']:
        item['comprovante'] = comprovantes_map.get(item['morador'].id)

    total_recebido = Mensalidade.objects.filter(pago=True).aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    total_expr = ExpressionWrapper(
        Case(
            When(nota__quantidade__gt=0, then=F('nota__quantidade') * F('nota__valor')),
            default=F('nota__valor'),
            output_field=DecimalField(max_digits=12, decimal_places=2),
        ),
        output_field=DecimalField(max_digits=12, decimal_places=2),
    )
    parcelas_notas = NotaParcela.objects.filter(
        mes_referencia=mes_referencia,
        nota__setor='compras',
    ).select_related('nota').annotate(total_valor=total_expr).order_by('-vencimento', '-id')
    return render(request, 'core/financeiro.html', {
        'total_recebido': total_recebido,
        'saldo': total_recebido - resumo['total_despesas'],
        'notas': parcelas_notas,
        'configuracao_form': configuracao_form,
        'parcelas_abertas': resumo['parcelas_rateio'].filter(status='pendente').order_by('vencimento', 'id'),
        'mes_referencia': mes_referencia,
        'mes_anterior': (mes_referencia - timedelta(days=1)).replace(day=1),
        'mes_proximo': (mes_referencia + timedelta(days=32)).replace(day=1),
        'desconto_form': DescontoMensalForm(),
        'pendencia_formset': PendenciaMensalItemFormSet(
            queryset=PendenciaMensalItem.objects.filter(mes_referencia=mes_referencia).order_by('id'),
            prefix='pendencia',
        ),
        'ajuste_formset': AjusteMoradorFormSet(
            queryset=AjusteMorador.objects.filter(mes_referencia=mes_referencia).order_by('id'),
            prefix='ajuste',
        ),
        'fixas_formset': ContaFixaFormSet(queryset=ContaFixa.objects.all()),
        'rateio_colspan': 8 + len(resumo['contas_fixas']),
        'can_edit_financeiro': can_edit_financeiro,
        **resumo,
    })


@setor_required(group_name='Financeiro', morador_view_attr='acesso_financeiro_visualizar', morador_edit_attr='acesso_financeiro_editar')
def exportar_financeiro_csv(request):
    mes_referencia = resolver_mes_referencia(request.GET.get('mes'))
    resumo = calcular_rateio_financeiro(mes_referencia, incluir_pendencia=False)
    total_recebido = Mensalidade.objects.filter(pago=True).aggregate(Sum('valor'))['valor__sum'] or Decimal('0.00')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="financeiro_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Resumo Financeiro'])
    writer.writerow(['Mes de Referencia', mes_referencia.strftime('%m/%Y')])
    writer.writerow(['Total Recebido', total_recebido])
    writer.writerow(['Despesas Pagas', resumo['total_despesas']])
    return response


@require_POST
@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def pagar_nota(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id)
    if nota.status != 'pago':
        nota.status = 'pago'
        nota.data_pagamento = timezone.now().date()
        nota.save(update_fields=['status', 'data_pagamento'])
    return redirect('financeiro')


@require_POST
@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def pagar_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela, id=parcela_id)
    if parcela.status != 'pago':
        parcela.status = 'pago'
        parcela.save(update_fields=['status'])
    return redirect('financeiro')


@require_POST
@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def anexar_comprovante_pagamento(request, morador_id):
    morador = get_object_or_404(Morador, id=morador_id, ativo=True)
    arquivo = request.FILES.get('comprovante')
    mes_param = request.POST.get('mes')

    if not arquivo or not mes_param:
        return redirect('financeiro')

    mes_referencia = resolver_mes_referencia(mes_param)
    ComprovantePagamentoMorador.objects.update_or_create(
        morador=morador,
        mes_referencia=mes_referencia,
        defaults={'arquivo': arquivo},
    )
    return redirect(f"{redirect('financeiro').url}?mes={mes_referencia.strftime('%Y-%m')}")


@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def editar_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela, id=parcela_id)
    form = ParcelaForm(request.POST or None, instance=parcela)
    if request.method == 'POST' and form.is_valid():
        form.save()
        return redirect('financeiro')
    return render(request, 'core/editar_parcela.html', {'form': form, 'parcela': parcela})


@setor_required(group_name='Financeiro', morador_edit_attr='acesso_financeiro_editar')
def editar_rateio_parcela(request, parcela_id):
    parcela = get_object_or_404(NotaParcela.objects.select_related('nota'), id=parcela_id)
    moradores_ativos = list(Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome'))
    if request.method == 'POST':
        selecionados = {int(mid) for mid in request.POST.getlist('moradores_rateio') if mid.isdigit()}
        ativos_ids = {morador.id for morador in moradores_ativos}
        if not selecionados:
            selecionados = set(ativos_ids)
        excluidos = ativos_ids - selecionados
        ParcelaRateioExclusao.objects.filter(parcela=parcela).exclude(morador_id__in=excluidos).delete()
        existentes = set(ParcelaRateioExclusao.objects.filter(parcela=parcela).values_list('morador_id', flat=True))
        for morador_id in excluidos - existentes:
            ParcelaRateioExclusao.objects.create(parcela=parcela, morador_id=morador_id)
        mes_param = request.POST.get('mes_param')
        return redirect(f"{redirect('financeiro').url}?mes={mes_param}") if mes_param else redirect('financeiro')

    excluidos_ids = set(ParcelaRateioExclusao.objects.filter(parcela=parcela).values_list('morador_id', flat=True))
    moradores_contexto = [{'morador': morador, 'selecionado': morador.id not in excluidos_ids} for morador in moradores_ativos]
    return render(request, 'core/editar_rateio_parcela.html', {
        'parcela': parcela,
        'moradores_contexto': moradores_contexto,
    })


def _primeiro_vencimento(data_emissao):
    mes = (data_emissao.replace(day=1) + timedelta(days=32)).replace(day=1) if data_emissao.day >= 5 else data_emissao.replace(day=1)
    return mes.replace(day=5), mes


def criar_parcelas_nota(nota):
    if nota.parcelas.exists():
        return
    quantidade = nota.quantidade_parcelas or 1
    total = (nota.valor or Decimal('0.00')) * (nota.quantidade or 0)
    vencimento, mes_ref = _primeiro_vencimento(nota.data_emissao)
    valor_parcela = (total / quantidade).quantize(Decimal('0.01')) if quantidade else total
    restante = total
    for idx in range(1, quantidade + 1):
        valor = valor_parcela if idx < quantidade else restante.quantize(Decimal('0.01'))
        NotaParcela.objects.create(nota=nota, numero=idx, valor=valor, vencimento=vencimento, mes_referencia=mes_ref, status='pendente')
        restante -= valor
        mes_ref = (mes_ref + timedelta(days=32)).replace(day=1)
        vencimento = mes_ref.replace(day=5)


@setor_required(group_name='Compras', morador_view_attr='acesso_compras_visualizar', morador_edit_attr='acesso_compras_editar')
def compras(request):
    can_edit_compras = can_edit(request, 'acesso_compras_editar')
    garantir_setores_e_locais_base()
    form = NotaFiscalForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        nota = form.save(commit=False)
        nota.setor = 'compras'
        if not nota.parcelado:
            nota.quantidade_parcelas = 1
        if not nota.adicionar_estoque:
            nota.setor_estoque = None
            nota.local_estoque = None
            nota.quantidade = 0
            nota.qualidade = ''
        nota.save()
        if nota.adicionar_estoque and nota.quantidade > 0:
            produto, criado = Produto.objects.get_or_create(nome=nota.descricao, setor=nota.setor_estoque, local=nota.local_estoque, defaults={'descricao': nota.tipo_item or '', 'quantidade': nota.quantidade, 'estoque_minimo': 0})
            if not criado:
                produto.quantidade += nota.quantidade
                if nota.tipo_item and produto.descricao != nota.tipo_item:
                    produto.descricao = nota.tipo_item
                produto.save(update_fields=['quantidade', 'descricao'])
        criar_parcelas_nota(nota)
        return redirect('compras')
    mes_cobranca_sub = NotaParcela.objects.filter(nota_id=OuterRef('pk')).order_by('mes_referencia').values('mes_referencia')[:1]
    notas = NotaFiscal.objects.filter(setor='compras').annotate(total_valor=ExpressionWrapper(F('quantidade') * F('valor'), output_field=DecimalField(max_digits=12, decimal_places=2)), mes_cobranca=Subquery(mes_cobranca_sub)).order_by('-data_emissao')
    return render(request, 'core/compras.html', {'form': form, 'notas': notas, 'can_edit_compras': can_edit_compras, 'comodos': Comodo.objects.select_related('andar').order_by('andar__nome', 'nome'), 'locais': LocalArmazenamento.objects.select_related('comodo').order_by('nome')})


@setor_required(group_name='Compras', morador_view_attr='acesso_compras_visualizar')
def exportar_compras_csv(request):
    notas = NotaFiscal.objects.filter(setor='compras').annotate(total_valor=ExpressionWrapper(F('quantidade') * F('valor'), output_field=DecimalField(max_digits=12, decimal_places=2))).order_by('-data_emissao', '-id')
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="compras_{timezone.localtime().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')
    writer = csv.writer(response, delimiter=';')
    writer.writerow(['Notas de Compras'])
    for nota in notas:
        writer.writerow([nota.descricao, nota.fornecedor, nota.valor, nota.total_valor])
    return response


@setor_required(group_name='Compras', morador_edit_attr='acesso_compras_editar')
def editar_nota_compra(request, nota_id):
    nota = get_object_or_404(NotaFiscal, id=nota_id, setor='compras')
    if request.method == 'POST' and 'excluir_submit' in request.POST:
        nota.delete()
        return redirect('compras')
    form = NotaFiscalForm(request.POST or None, instance=nota)
    if request.method == 'POST' and form.is_valid():
        nota = form.save(commit=False)
        nota.setor = 'compras'
        if not nota.adicionar_estoque:
            nota.setor_estoque = None
            nota.local_estoque = None
            nota.quantidade = 0
            nota.qualidade = ''
        nota.save()
        messages.success(request, 'Nota atualizada com sucesso.')
        return redirect('compras')
    return render(request, 'core/editar_nota.html', {'form': form, 'nota': nota, 'comodos': Comodo.objects.select_related('andar').order_by('andar__nome', 'nome'), 'locais': LocalArmazenamento.objects.select_related('comodo').order_by('nome')})

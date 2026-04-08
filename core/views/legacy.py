"""Módulo legado residual.

Mantém apenas telas administrativas de configuração enquanto os domínios
foram migrados para módulos dedicados.
"""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.forms import modelformset_factory
from django.shortcuts import redirect, render

from core.forms import (
    AcessoMoradorForm,
    AjusteMoradorForm,
    CadastroForm,
    ConfiguracaoFinanceiraForm,
    ConsumoForm,
    ContaFixaForm,
    DescontoMensalForm,
    MaterialUtilizadoForm,
    MovimentacaoForm,
    OrdemServicoForm,
    PerfilFotoForm,
    ProdutoForm,
    RockEventoForm,
)
from core.models import Andar, ChoiceList, ChoiceOption, Comodo, FormFieldConfig, LocalArmazenamento, Setor
from core.views.financeiro import NotaFiscalForm
from core.forms import MoradorEdicaoForm


@login_required
def configurar_formularios(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Voce nao tem permissao para acessar este modulo.')

    form_registry = [
        ('nota_fiscal_form', 'Compras - Nota Fiscal', NotaFiscalForm),
        ('produto_form', 'Almoxarifado - Produto', ProdutoForm),
        ('movimentacao_form', 'Almoxarifado - Movimentacao', MovimentacaoForm),
        ('consumo_form', 'Almoxarifado - Consumo', ConsumoForm),
        ('ordem_servico_form', 'Manutencao - Ordem de Servico', OrdemServicoForm),
        ('material_utilizado_form', 'Manutencao - Material Utilizado', MaterialUtilizadoForm),
        ('configuracao_financeira_form', 'Financeiro - Configuracao', ConfiguracaoFinanceiraForm),
        ('desconto_mensal_form', 'Financeiro - Desconto', DescontoMensalForm),
        ('ajuste_morador_form', 'Financeiro - Ajuste Morador', AjusteMoradorForm),
        ('conta_fixa_form', 'Financeiro - Conta Fixa', ContaFixaForm),
        ('cadastro_form', 'Cadastro', CadastroForm),
        ('perfil_foto_form', 'Perfil - Foto', PerfilFotoForm),
        ('acesso_morador_form', 'Morador - Acessos', AcessoMoradorForm),
        ('morador_edicao_form', 'Morador - Edicao', MoradorEdicaoForm),
        ('rock_evento_form', 'Rock - Evento', RockEventoForm),
    ]

    if request.method == 'POST':
        for form_key, _label, form_class in form_registry:
            form = form_class()
            for idx, field_name in enumerate(form.fields.keys(), start=1):
                label_value = request.POST.get(f'{form_key}__{field_name}__label', '').strip()
                visible_value = request.POST.get(f'{form_key}__{field_name}__visible') == 'on'
                order_value = request.POST.get(f'{form_key}__{field_name}__order', '').strip()
                order = int(order_value) if order_value.isdigit() else idx
                FormFieldConfig.objects.update_or_create(form_key=form_key, field_name=field_name, defaults={'label': label_value, 'visible': visible_value, 'order': order})
        return redirect('configurar_formularios')

    forms_data = []
    for form_key, label, form_class in form_registry:
        form = form_class()
        configs = {cfg.field_name: cfg for cfg in FormFieldConfig.objects.filter(form_key=form_key)}
        fields = [{'name': name, 'label': configs[name].label if name in configs and configs[name].label else field.label, 'visible': configs[name].visible if name in configs else True, 'order': configs[name].order if name in configs else idx} for idx, (name, field) in enumerate(form.fields.items(), start=1)]
        forms_data.append({'key': form_key, 'label': label, 'fields': fields})

    return render(request, 'core/configurar_formularios.html', {'forms': forms_data})


@login_required
def configurar_listas(request):
    if not request.user.is_superuser:
        raise PermissionDenied('Voce nao tem permissao para acessar este modulo.')

    list_registry = [
        ('produto_descricao', 'Produto - Tipo'),
        ('nota_tipo_item', 'Compras - Tipo de item'),
        ('categoria_compra', 'Compras - Categoria'),
        ('movimentacao_tipo', 'Almoxarifado - Tipo de movimentacao'),
        ('consumo_setor', 'Almoxarifado - Setor de consumo'),
        ('morador_funcoes', 'Moradores - Funcoes'),
    ]
    for key, label in list_registry:
        ChoiceList.objects.get_or_create(key=key, defaults={'label': label})

    ChoiceOptionFormSet = modelformset_factory(ChoiceOption, fields=('value', 'label', 'order', 'active'), extra=1, can_delete=True)
    SetorFormSet = modelformset_factory(Setor, fields=('nome',), extra=1, can_delete=True)
    AndarFormSet = modelformset_factory(Andar, fields=('nome',), extra=1, can_delete=True)
    ComodoFormSet = modelformset_factory(Comodo, fields=('nome', 'andar'), extra=1, can_delete=True)
    LocalFormSet = modelformset_factory(LocalArmazenamento, fields=('nome', 'comodo'), extra=1, can_delete=True)

    setor_formset = SetorFormSet(queryset=Setor.objects.all(), prefix='setor')
    andar_formset = AndarFormSet(queryset=Andar.objects.all(), prefix='andar')
    comodo_formset = ComodoFormSet(queryset=Comodo.objects.select_related('andar'), prefix='comodo')
    local_formset = LocalFormSet(queryset=LocalArmazenamento.objects.select_related('comodo'), prefix='local')

    list_formsets = []
    for key, _label in list_registry:
        choice_list = ChoiceList.objects.get(key=key)
        list_formsets.append((choice_list, ChoiceOptionFormSet(queryset=ChoiceOption.objects.filter(choice_list=choice_list), prefix=key)))

    if request.method == 'POST':
        section = request.POST.get('config_section')
        if section == 'estrutura':
            andar_formset = AndarFormSet(request.POST, queryset=Andar.objects.all(), prefix='andar')
            comodo_formset = ComodoFormSet(request.POST, queryset=Comodo.objects.select_related('andar'), prefix='comodo')
            local_formset = LocalFormSet(request.POST, queryset=LocalArmazenamento.objects.select_related('comodo'), prefix='local')
            if andar_formset.is_valid() and comodo_formset.is_valid() and local_formset.is_valid():
                andar_formset.save(); comodo_formset.save(); local_formset.save(); return redirect('configurar_listas')
        elif section == 'setores':
            setor_formset = SetorFormSet(request.POST, queryset=Setor.objects.all(), prefix='setor')
            if setor_formset.is_valid():
                setor_formset.save(); return redirect('configurar_listas')

    return render(request, 'core/configurar_listas.html', {'setor_formset': setor_formset, 'andar_formset': andar_formset, 'comodo_formset': comodo_formset, 'local_formset': local_formset, 'list_formsets': list_formsets})

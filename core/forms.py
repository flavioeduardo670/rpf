from collections import OrderedDict
import os
import uuid
from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils.text import get_valid_filename
from django.utils import timezone
from django.db.models import Case, F, IntegerField, When
from .models import (
    ChoiceList,
    ChoiceOption,
    AcessoUsuario,
    EventoCalendario,
    FormFieldConfig,
    Morador,
    ConsumoEstoque,
    Comodo,
    LocalArmazenamento,
    Produto,
    MovimentacaoEstoque,
    OrdemServico,
    MaterialUtilizado,
    ConfiguracaoFinanceira,
    Setor,
    RockEvento,
    RockItem,
    IngressoRock,
    LoteIngressoRock,
    DescontoMensal,
    PendenciaMensal,
    PendenciaMensalItem,
    AjusteMorador,
    ContaFixa,
    AtaReuniao,
)


def apply_form_config(form, form_key):
    configs = list(FormFieldConfig.objects.filter(form_key=form_key))
    if not configs:
        return

    config_map = {cfg.field_name: cfg for cfg in configs}
    fields = list(form.fields.items())
    for name, field in fields:
        cfg = config_map.get(name)
        if not cfg:
            continue
        if cfg.label:
            field.label = cfg.label
        if not cfg.visible:
            field.required = False
            field.widget = forms.HiddenInput()

    def sort_key(item):
        name = item[0]
        cfg = config_map.get(name)
        if cfg:
            return (0, cfg.order, name)
        return (1, 9999, name)

    form.fields = OrderedDict(sorted(form.fields.items(), key=sort_key))


def get_choice_options(list_key, default_choices):
    choice_list = ChoiceList.objects.filter(key=list_key).first()
    if not choice_list:
        return default_choices
    options = ChoiceOption.objects.filter(choice_list=choice_list, active=True).order_by('order', 'label')
    if not options.exists():
        return default_choices
    return [(opt.value, opt.label) for opt in options]


# =========================
# ESTOQUE
# =========================

class ProdutoForm(forms.ModelForm):
    comodo = forms.ModelChoiceField(
        queryset=Comodo.objects.none(),
        required=False,
        label='Cômodo',
    )

    class Meta:
        model = Produto
        fields = ['nome', 'descricao', 'setor', 'local', 'quantidade', 'estoque_minimo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['local'].required = False
        self.fields['descricao'] = forms.ChoiceField(
            choices=get_choice_options(
                'produto_descricao',
                [
                    ('', '---'),
                    ('Bem de Uso', 'Bem de Uso'),
                    ('Bem de Consumo', 'Bem de Consumo'),
                    ('Bem de Troca', 'Bem de Troca'),
                ],
            ),
            required=False,
        )
        if self.data:
            descricao_key = self.add_prefix('descricao')
            descricao_val = self.data.get(descricao_key)
            if descricao_val:
                escolhas = {choice[0] for choice in self.fields['descricao'].choices}
                if descricao_val not in escolhas:
                    self.fields['descricao'].choices.append((descricao_val, descricao_val))
        self.fields['descricao'].widget.attrs.update({'style': 'min-height:34px;'})

        setor_nomes = ['Infraestrutura', 'Hotelaria', 'Rock', 'Estoque']
        setor_qs = Setor.objects.filter(nome__in=setor_nomes)
        if setor_qs.exists():
            setor_ordem = Case(
                *[When(nome=nome, then=pos) for pos, nome in enumerate(setor_nomes)],
                output_field=IntegerField(),
            )
            self.fields['setor'].queryset = setor_qs.order_by(setor_ordem)

        self.fields['comodo'].queryset = Comodo.objects.select_related('andar').order_by('andar__nome', 'nome')
        selected_comodo = None
        if self.data:
            comodo_val = self.data.get(self.add_prefix('comodo'))
            if comodo_val:
                selected_comodo = Comodo.objects.filter(pk=comodo_val).first()
        elif self.instance and self.instance.pk and self.instance.local and self.instance.local.comodo_id:
            selected_comodo = self.instance.local.comodo

        if selected_comodo:
            self.fields['local'].queryset = LocalArmazenamento.objects.filter(
                comodo=selected_comodo
            ).order_by('nome')
            self.fields['comodo'].initial = selected_comodo
        else:
            self.fields['local'].queryset = LocalArmazenamento.objects.none()
        apply_form_config(self, 'produto_form')


class MovimentacaoForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoEstoque
        fields = ['produto', 'tipo', 'quantidade']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['tipo'].choices = get_choice_options(
            'movimentacao_tipo',
            [('entrada', 'Entrada'), ('saida', 'Saida')],
        )
        apply_form_config(self, 'movimentacao_form')

    def clean_quantidade(self):
        quantidade = self.cleaned_data['quantidade']
        if quantidade <= 0:
            raise forms.ValidationError('A quantidade deve ser maior que zero.')
        return quantidade

    def clean(self):
        cleaned_data = super().clean()
        produto = cleaned_data.get('produto')
        tipo = cleaned_data.get('tipo')
        quantidade = cleaned_data.get('quantidade')

        if produto and tipo == 'saida' and quantidade and quantidade > produto.quantidade:
            self.add_error(
                'quantidade',
                f'Estoque insuficiente para {produto.nome}. Disponivel: {produto.quantidade}.',
            )

        return cleaned_data


class ConsumoForm(forms.ModelForm):
    class Meta:
        model = ConsumoEstoque
        fields = ['morador', 'data', 'produto', 'quantidade', 'setor', 'rock_evento']
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['morador'].queryset = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')
        self.fields['morador'].label_from_instance = (
            lambda m: (m.apelido or m.nome)
        )
        self.fields['rock_evento'].queryset = RockEvento.objects.order_by('-data')
        self.fields['rock_evento'].required = False
        self.fields['setor'].choices = get_choice_options(
            'consumo_setor',
            [
                ('infraestrutura', 'Infraestrutura'),
                ('rock', 'Rock'),
                ('outros', 'Outros'),
            ],
        )
        apply_form_config(self, 'consumo_form')

    def clean_quantidade(self):
        quantidade = self.cleaned_data['quantidade']
        if quantidade <= 0:
            raise forms.ValidationError('A quantidade deve ser maior que zero.')
        return quantidade

    def clean(self):
        cleaned_data = super().clean()
        produto = cleaned_data.get('produto')
        quantidade = cleaned_data.get('quantidade')

        if produto and quantidade and quantidade > produto.quantidade:
            self.add_error(
                'quantidade',
                f'Estoque insuficiente para {produto.nome}. Disponivel: {produto.quantidade}.',
            )

        return cleaned_data


# =========================
# MANUTENÇÃO
# =========================

class OrdemServicoForm(forms.ModelForm):
    class Meta:
        model = OrdemServico
        fields = [
            'setor',
            'descricao',
            'observacao',
            'data_inicio',
            'data_fim',
            'executado_por',
            'status'
        ]
        widgets = {
            'data_inicio': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
            'data_fim': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        moradores = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')
        self.fields['executado_por'] = forms.ChoiceField(
            choices=[('', '---')] + [
                (m.nome, m.apelido or m.nome) for m in moradores
            ],
            required=True,
            label='Executado por',
        )
        apply_form_config(self, 'ordem_servico_form')


class MaterialUtilizadoForm(forms.ModelForm):
    class Meta:
        model = MaterialUtilizado
        fields = [
            'produto',
            'quantidade',
            'morador',
            'data_consumo',
        ]
        widgets = {
            'data_consumo': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        setores = ['Infraestrutura', 'Manutencao']
        self.fields['produto'].queryset = Produto.objects.filter(
            setor__nome__in=setores
        ).select_related('setor', 'local').order_by('nome')
        self.fields['morador'].queryset = Morador.objects.filter(
            ativo=True
        ).order_by('ordem_hierarquia', 'nome')
        self.fields['morador'].label_from_instance = (
            lambda m: (m.apelido or m.nome)
        )
        self.fields['data_consumo'].required = True
        if not self.instance.pk and not self.initial.get('data_consumo'):
            self.initial['data_consumo'] = timezone.localdate()
        apply_form_config(self, 'material_utilizado_form')

    def clean_quantidade(self):
        quantidade = self.cleaned_data['quantidade']
        if quantidade <= 0:
            raise forms.ValidationError('A quantidade deve ser maior que zero.')
        return quantidade

    def clean(self):
        cleaned_data = super().clean()
        produto = cleaned_data.get('produto')
        quantidade = cleaned_data.get('quantidade')
        setor = cleaned_data.get('setor')
        rock_evento = cleaned_data.get('rock_evento')

        if produto and quantidade:
            consumo = getattr(self.instance, 'consumo', None)
            if consumo and consumo.produto_id == produto.id:
                disponivel = produto.quantidade + consumo.quantidade
            else:
                disponivel = produto.quantidade

            if quantidade > disponivel:
                self.add_error(
                    'quantidade',
                    f'Estoque insuficiente para {produto.nome}. Disponivel: {disponivel}.',
                )

        if setor == 'rock' and not rock_evento:
            self.add_error('rock_evento', 'Selecione o rock relacionado.')

        return cleaned_data


class ConfiguracaoFinanceiraForm(forms.ModelForm):
    class Meta:
        model = ConfiguracaoFinanceira
        fields = [
            'valor_aluguel',
            'valor_agua',
            'valor_luz',
            'conta_principal_pix',
            'conta_recebimentos_pix',
            'conta_pagamentos_pix',
        ]
        labels = {
            'valor_aluguel': 'Aluguel',
            'valor_agua': 'Conta de agua',
            'valor_luz': 'Conta de luz',
            'conta_principal_pix': 'PIX conta principal',
            'conta_recebimentos_pix': 'PIX conta de recebimentos',
            'conta_pagamentos_pix': 'PIX conta de pagamentos',
        }
        widgets = {
            'valor_aluguel': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'valor_agua': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'valor_luz': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'conta_principal_pix': forms.TextInput(attrs={'placeholder': 'Chave PIX da conta principal'}),
            'conta_recebimentos_pix': forms.TextInput(attrs={'placeholder': 'Chave PIX para receber pagamentos'}),
            'conta_pagamentos_pix': forms.TextInput(attrs={'placeholder': 'Chave PIX da conta de pagamentos'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'configuracao_financeira_form')


class PerfilFotoForm(forms.ModelForm):
    ALLOWED_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp'}
    ALLOWED_CONTENT_TYPES = {'image/jpeg', 'image/png', 'image/webp'}
    MAX_FILE_SIZE = 2 * 1024 * 1024  # 2MB

    class Meta:
        model = Morador
        fields = ['foto_perfil']
        labels = {'foto_perfil': 'Foto de perfil'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'perfil_foto_form')

    def clean_foto_perfil(self):
        foto = self.cleaned_data.get('foto_perfil')
        if not foto:
            return foto

        original_name = foto.name or 'foto-perfil'
        _, ext = os.path.splitext(original_name)
        ext = ext.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            raise forms.ValidationError('Use uma imagem JPG, JPEG, PNG ou WEBP.')

        content_type = (getattr(foto, 'content_type', '') or '').lower()
        if content_type not in self.ALLOWED_CONTENT_TYPES:
            raise forms.ValidationError('O arquivo enviado nao e uma imagem valida.')

        if foto.size > self.MAX_FILE_SIZE:
            raise forms.ValidationError('A imagem deve ter no maximo 2MB.')

        nome_base = get_valid_filename(os.path.splitext(original_name)[0]) or 'foto-perfil'
        foto.name = f'{nome_base}-{uuid.uuid4().hex[:8]}{ext}'
        return foto


class RockEventoForm(forms.ModelForm):
    class Meta:
        model = RockEvento
        fields = [
            'nome',
            'tipo',
            'quantidade_pessoas',
            'horario_inicio',
            'horario_fim',
            'observacoes',
            'data',
            'valor_arrecadado',
        ]
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
            'horario_inicio': forms.TimeInput(attrs={'type': 'time'}),
            'horario_fim': forms.TimeInput(attrs={'type': 'time'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'rock_evento_form')


class RockItemForm(forms.ModelForm):
    class Meta:
        model = RockItem
        fields = ['produto', 'quantidade', 'valor_unitario', 'observacao']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['produto'].queryset = Produto.objects.filter(descricao='Bem de Troca').order_by('nome')
        self.fields['produto'].required = True

    def clean(self):
        cleaned = super().clean()
        produto = cleaned.get('produto')
        if not produto:
            raise forms.ValidationError('Selecione um produto para o item do rock.')
        return cleaned


class IngressoRockForm(forms.ModelForm):
    lote = forms.ModelChoiceField(
        queryset=LoteIngressoRock.objects.none(),
        label='Lote',
    )

    class Meta:
        model = IngressoRock
        fields = ['nome', 'telefone', 'lote', 'quantidade_ingressos', 'status_pagamento', 'observacao']

    def __init__(self, *args, evento=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantidade_ingressos'].widget = forms.NumberInput(attrs={'min': '1'})
        lotes = LoteIngressoRock.objects.none()
        if evento:
            lotes = evento.lotes.filter(quantidade_total__gt=F('quantidade_vendida')).order_by('id')
        self.fields['lote'].queryset = lotes

    def clean(self):
        cleaned = super().clean()
        lote = cleaned.get('lote')
        quantidade = cleaned.get('quantidade_ingressos') or 0
        if lote and quantidade > lote.quantidade_disponivel:
            raise forms.ValidationError('Quantidade solicitada maior que o disponivel no lote.')
        return cleaned

    def save(self, commit=True):
        lote = self.cleaned_data.get('lote')
        self.instance.valor_unitario = lote.preco if lote else 0
        if lote and not self.instance.observacao:
            self.instance.observacao = f'Lote: {lote.nome}'
        return super().save(commit=commit)


class LoteIngressoRockForm(forms.ModelForm):
    class Meta:
        model = LoteIngressoRock
        fields = ['nome', 'quantidade_total', 'preco']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['quantidade_total'].widget = forms.NumberInput(attrs={'min': '1'})
        self.fields['preco'].widget = forms.NumberInput(attrs={'step': '0.01', 'min': '0'})


class CompraIngressoRockForm(forms.Form):
    lote = forms.ModelChoiceField(queryset=LoteIngressoRock.objects.none(), label='Lote')
    nome_comprador = forms.CharField(max_length=150, label='Nome')
    telefone = forms.CharField(max_length=30, required=False, label='Telefone')
    quantidade = forms.IntegerField(min_value=1, initial=1, label='Quantidade de ingressos')

    def __init__(self, *args, lotes_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['lote'].queryset = lotes_queryset or LoteIngressoRock.objects.none()

    def clean(self):
        cleaned = super().clean()
        lote = cleaned.get('lote')
        quantidade = cleaned.get('quantidade') or 0
        if lote and quantidade > lote.quantidade_disponivel:
            raise forms.ValidationError('Quantidade solicitada maior que o disponivel no lote.')
        return cleaned


class EventoCalendarioForm(forms.ModelForm):
    class Meta:
        model = EventoCalendario
        fields = ['titulo', 'data']
        labels = {
            'titulo': 'Evento',
            'data': 'Data',
        }
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
        }


class DescontoMensalForm(forms.ModelForm):
    class Meta:
        model = DescontoMensal
        fields = ['valor_total']
        labels = {'valor_total': 'Desconto total do mes'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'desconto_mensal_form')


class PendenciaMensalForm(forms.ModelForm):
    class Meta:
        model = PendenciaMensal
        fields = ['valor_total']
        labels = {'valor_total': 'Pendencia total do mes'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'pendencia_mensal_form')


class PendenciaMensalItemForm(forms.ModelForm):
    class Meta:
        model = PendenciaMensalItem
        fields = ['tipo', 'valor', 'motivo']
        labels = {'tipo': 'Tipo', 'valor': 'Valor', 'motivo': 'Motivo'}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['motivo'].required = False
        apply_form_config(self, 'pendencia_mensal_item_form')


class AjusteMoradorForm(forms.ModelForm):
    class Meta:
        model = AjusteMorador
        fields = ['morador', 'tipo', 'valor', 'motivo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['morador'].queryset = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')
        self.fields['morador'].label_from_instance = lambda m: (m.apelido or m.nome)
        apply_form_config(self, 'ajuste_morador_form')


class ContaFixaForm(forms.ModelForm):
    class Meta:
        model = ContaFixa
        fields = ['nome', 'valor', 'ativo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'conta_fixa_form')


class AtaReuniaoForm(forms.ModelForm):
    class Meta:
        model = AtaReuniao
        fields = [
            'horario_inicio_real',
            'horario_fim_real',
            'texto_abertura',
            'participantes_texto',
            'topicos_texto',
            'plano_acao_5w2h_texto',
            'encerramento_texto',
        ]
        labels = {
            'texto_abertura': 'Abertura',
            'participantes_texto': 'Participantes (1 por linha)',
            'topicos_texto': 'Tópicos (1 por linha)',
            'plano_acao_5w2h_texto': '5W2H (What|Why|Where|When|Who|How|How much por linha)',
            'encerramento_texto': 'Encerramento',
        }
        widgets = {
            'horario_inicio_real': forms.TimeInput(attrs={'type': 'time'}),
            'horario_fim_real': forms.TimeInput(attrs={'type': 'time'}),
            'texto_abertura': forms.Textarea(attrs={'rows': 4}),
            'participantes_texto': forms.Textarea(attrs={'rows': 6}),
            'topicos_texto': forms.Textarea(attrs={'rows': 6}),
            'plano_acao_5w2h_texto': forms.Textarea(attrs={'rows': 8}),
            'encerramento_texto': forms.Textarea(attrs={'rows': 4}),
        }


class CadastroForm(UserCreationForm):
    email = forms.EmailField(required=False, label='Email')

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'cadastro_form')

    def save(self, commit=True):
        user = super().save(commit=commit)
        if commit:
            AcessoUsuario.objects.get_or_create(user=user)
        return user


class AcessoMoradorForm(forms.ModelForm):
    class Meta:
        model = Morador
        fields = [
            'acesso_financeiro_visualizar',
            'acesso_financeiro_editar',
            'acesso_compras_visualizar',
            'acesso_compras_editar',
            'acesso_estoque_visualizar',
            'acesso_estoque_editar',
            'acesso_manutencao_visualizar',
            'acesso_manutencao_editar',
            'acesso_rock_visualizar',
            'acesso_rock_editar',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'acesso_morador_form')


class AcessoUsuarioForm(forms.ModelForm):
    class Meta:
        model = AcessoUsuario
        fields = [
            'acesso_financeiro_visualizar',
            'acesso_financeiro_editar',
            'acesso_compras_visualizar',
            'acesso_compras_editar',
            'acesso_estoque_visualizar',
            'acesso_estoque_editar',
            'acesso_manutencao_visualizar',
            'acesso_manutencao_editar',
            'acesso_rock_visualizar',
            'acesso_rock_editar',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        apply_form_config(self, 'acesso_morador_form')


class MoradorEdicaoForm(forms.ModelForm):
    class Meta:
        model = Morador
        fields = [
            'ordem_hierarquia',
            'nome',
            'apelido',
            'email',
            'codigo_quarto',
            'quarto',
            'curso',
            'funcoes',
            'ativo',
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['funcoes'] = forms.ChoiceField(
            choices=get_choice_options(
                'morador_funcoes',
                [
                    ('Financeiro', 'Financeiro'),
                    ('Rock', 'Rock'),
                    ('Infraestrutura', 'Infraestrutura'),
                    ('Hotelaria', 'Hotelaria'),
                    ('Almoxarifado', 'Almoxarifado'),
                    ('Marketing', 'Marketing'),
                ],
            ),
            required=False,
            label='Funcoes',
        )
        apply_form_config(self, 'morador_edicao_form')

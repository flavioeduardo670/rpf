from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.utils import timezone
from django.db.models import Case, IntegerField, When
from .models import (
    Morador,
    ConsumoEstoque,
    LocalArmazenamento,
    Produto,
    MovimentacaoEstoque,
    OrdemServico,
    MaterialUtilizado,
    ConfiguracaoFinanceira,
    Setor,
    RockEvento,
    DescontoMensal,
    PendenciaMensal,
    AjusteMorador,
    ContaFixa,
)


# =========================
# ESTOQUE
# =========================

class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = ['nome', 'descricao', 'setor', 'local', 'quantidade', 'estoque_minimo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['local'].required = False
        self.fields['descricao'] = forms.ChoiceField(
            choices=[
                ('', '---'),
                ('Bem de Uso', 'Bem de Uso'),
                ('Bem de Consumo', 'Bem de Consumo'),
                ('Bem de Troca', 'Bem de Troca'),
            ],
            required=False,
        )
        self.fields['descricao'].widget.attrs.update({'style': 'min-height:34px;'})

        setor_nomes = ['Infraestrutura', 'Hotelaria', 'Rock']
        setor_qs = Setor.objects.filter(nome__in=setor_nomes)
        if setor_qs.exists():
            setor_ordem = Case(
                *[When(nome=nome, then=pos) for pos, nome in enumerate(setor_nomes)],
                output_field=IntegerField(),
            )
            self.fields['setor'].queryset = setor_qs.order_by(setor_ordem)

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
        local_qs = LocalArmazenamento.objects.filter(nome__in=local_nomes)
        if local_qs.exists():
            local_ordem = Case(
                *[When(nome=nome, then=pos) for pos, nome in enumerate(local_nomes)],
                output_field=IntegerField(),
            )
            self.fields['local'].queryset = local_qs.order_by(local_ordem)


class MovimentacaoForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoEstoque
        fields = ['produto', 'tipo', 'quantidade']

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
        fields = ['valor_aluguel', 'valor_agua', 'valor_luz']
        labels = {
            'valor_aluguel': 'Aluguel',
            'valor_agua': 'Conta de agua',
            'valor_luz': 'Conta de luz',
        }
        widgets = {
            'valor_aluguel': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'valor_agua': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
            'valor_luz': forms.NumberInput(attrs={'step': '0.01', 'min': '0'}),
        }


class PerfilFotoForm(forms.ModelForm):
    class Meta:
        model = Morador
        fields = ['foto_perfil']
        labels = {'foto_perfil': 'Foto de perfil'}


class RockEventoForm(forms.ModelForm):
    class Meta:
        model = RockEvento
        fields = [
            'nome',
            'tipo',
            'quantidade_pessoas',
            'observacoes',
            'data',
            'valor_arrecadado',
        ]
        widgets = {
            'data': forms.DateInput(attrs={'type': 'date'}),
        }


class DescontoMensalForm(forms.ModelForm):
    class Meta:
        model = DescontoMensal
        fields = ['valor_total']
        labels = {'valor_total': 'Desconto total do mes'}


class PendenciaMensalForm(forms.ModelForm):
    class Meta:
        model = PendenciaMensal
        fields = ['valor_total']
        labels = {'valor_total': 'Pendencia total do mes'}


class AjusteMoradorForm(forms.ModelForm):
    class Meta:
        model = AjusteMorador
        fields = ['morador', 'tipo', 'valor', 'motivo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['morador'].queryset = Morador.objects.filter(ativo=True).order_by('ordem_hierarquia', 'nome')
        self.fields['morador'].label_from_instance = lambda m: (m.apelido or m.nome)


class ContaFixaForm(forms.ModelForm):
    class Meta:
        model = ContaFixa
        fields = ['nome', 'valor', 'ativo']


class CadastroForm(UserCreationForm):
    morador = forms.ModelChoiceField(
        queryset=Morador.objects.none(),
        required=True,
        label='Morador',
    )
    email = forms.EmailField(required=False, label='Email')

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ['username', 'email', 'morador', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['morador'].queryset = Morador.objects.filter(
            ativo=True,
            user__isnull=True,
        ).order_by('ordem_hierarquia', 'nome')
        self.fields['morador'].label_from_instance = lambda m: (m.apelido or m.nome)

    def save(self, commit=True):
        user = super().save(commit=commit)
        morador = self.cleaned_data.get('morador')
        if morador:
            morador.user = user
            if commit:
                morador.save(update_fields=['user'])
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

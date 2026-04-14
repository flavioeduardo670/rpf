from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import UserChangeForm, UserCreationForm
from django.contrib.auth.models import User
from django import forms

from .models import (
    AcessoUsuario,
    AtaParticipante,
    AtaReuniao,
    AtaTopico,
    ConfiguracaoFinanceira,
    Morador,
    Mensalidade,
    NotaFiscal,
    Reuniao,
)


# =====================================================
# MORADOR
# =====================================================

@admin.register(Morador)
class MoradorAdmin(admin.ModelAdmin):

    list_display = (
        'ordem_hierarquia',
        'nome',
        'apelido',
        'quarto',
        'codigo_quarto',
        'peso_quarto',
        'curso',
        'funcoes',
        'ativo',
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
    )

    list_filter = (
        'ativo',
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
    )

    search_fields = ('nome', 'apelido', 'email')

    fieldsets = (
        ('Dados Pessoais', {
            'fields': (
                'ordem_hierarquia',
                'nome',
                'apelido',
                'email',
                'quarto',
                'codigo_quarto',
                'peso_quarto',
                'curso',
                'funcoes',
                'ativo',
            )
        }),
        ('Permissoes de Acesso', {
            'fields': (
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
            )
        }),
    )

    ordering = ('ordem_hierarquia', 'nome')


# =====================================================
# OUTROS MODELS
# =====================================================

admin.site.register(Mensalidade)
admin.site.register(NotaFiscal)


@admin.register(Reuniao)
class ReuniaoAdmin(admin.ModelAdmin):
    list_display = ('id', 'tipo', 'setor', 'data', 'horario_marcado', 'local', 'status')
    list_filter = ('tipo', 'setor', 'status', 'data')
    search_fields = ('local',)
    ordering = ('-data', '-horario_marcado')


class AtaParticipanteInline(admin.TabularInline):
    model = AtaParticipante
    extra = 0
    autocomplete_fields = ('morador',)
    fields = ('morador', 'presente', 'assinatura_status')


class AtaTopicoInline(admin.StackedInline):
    model = AtaTopico
    extra = 0
    fields = ('ordem', 'titulo_assunto', 'desenvolvimento')
    ordering = ('ordem', 'id')


@admin.register(AtaReuniao)
class AtaReuniaoAdmin(admin.ModelAdmin):
    list_display = (
        'identificador_formatado',
        'reuniao',
        'numero_sequencial',
        'ano',
        'escopo_numeracao',
        'horario_inicio_real',
        'horario_fim_real',
        'criado_por',
        'criado_em',
    )
    list_filter = ('ano', 'escopo_numeracao', 'criado_em')
    search_fields = ('identificador_formatado', 'reuniao__local', 'reuniao__setor')
    autocomplete_fields = ('reuniao', 'criado_por')
    ordering = ('-ano', '-numero_sequencial')
    inlines = (AtaParticipanteInline, AtaTopicoInline)


@admin.register(ConfiguracaoFinanceira)
class ConfiguracaoFinanceiraAdmin(admin.ModelAdmin):
    list_display = (
        'valor_aluguel',
        'valor_agua',
        'valor_luz',
        'conta_principal_pix',
        'conta_recebimentos_pix',
        'conta_pagamentos_pix',
        'atualizado_em',
    )
    fieldsets = (
        ('Valores base', {'fields': ('valor_aluguel', 'valor_agua', 'valor_luz')}),
        (
            'Contas da casa (PIX)',
            {
                'fields': (
                    'conta_principal_pix',
                    'conta_recebimentos_pix',
                    'conta_pagamentos_pix',
                )
            },
        ),
    )


# Re-registra o User com formulario que permite vincular Morador.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


class UserAdminCreationForm(UserCreationForm):
    perfil_tipo = forms.ChoiceField(
        choices=[('visitante', 'Visitante de fora'), ('morador', 'Morador')],
        initial='visitante',
        label='Tipo de perfil',
    )
    morador = forms.ModelChoiceField(
        queryset=Morador.objects.none(),
        required=False,
        label='Morador vinculado',
        help_text='Selecione um morador apenas quando o tipo for Morador.',
    )

    class Meta(UserCreationForm.Meta):
        model = User
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['morador'].queryset = Morador.objects.filter(user__isnull=True).order_by('ordem_hierarquia', 'nome')

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('perfil_tipo') == 'morador' and not cleaned_data.get('morador'):
            self.add_error('morador', 'Selecione um morador para vincular este usuario.')
        return cleaned_data


class UserAdminChangeForm(UserChangeForm):
    perfil_tipo = forms.ChoiceField(
        choices=[('visitante', 'Visitante de fora'), ('morador', 'Morador')],
        initial='visitante',
        label='Tipo de perfil',
    )
    morador = forms.ModelChoiceField(
        queryset=Morador.objects.none(),
        required=False,
        label='Morador vinculado',
        help_text='Selecione um morador apenas quando o tipo for Morador.',
    )

    class Meta(UserChangeForm.Meta):
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        morador_atual = None
        try:
            morador_atual = self.instance.morador
        except Morador.DoesNotExist:
            morador_atual = None

        queryset = Morador.objects.filter(user__isnull=True)
        if morador_atual:
            queryset = Morador.objects.filter(pk=morador_atual.pk) | queryset
            self.initial['perfil_tipo'] = 'morador'
            self.initial['morador'] = morador_atual
        self.fields['morador'].queryset = queryset.order_by('ordem_hierarquia', 'nome')

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('perfil_tipo') == 'morador' and not cleaned_data.get('morador'):
            self.add_error('morador', 'Selecione um morador para vincular este usuario.')
        return cleaned_data


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = UserAdminCreationForm
    form = UserAdminChangeForm
    list_display = ('username', 'email', 'is_staff', 'is_superuser', 'tipo_cadastro')

    fieldsets = BaseUserAdmin.fieldsets + (
        ('Vinculo com a casa', {'fields': ('perfil_tipo', 'morador')}),
    )
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username', 'email', 'perfil_tipo', 'morador', 'password1', 'password2'),
            },
        ),
    )

    @admin.display(description='Tipo')
    def tipo_cadastro(self, obj):
        return 'Morador' if hasattr(obj, 'morador') else 'Visitante'

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        AcessoUsuario.objects.get_or_create(user=obj)

        perfil_tipo = form.cleaned_data.get('perfil_tipo')
        morador_selecionado = form.cleaned_data.get('morador')

        morador_atual = None
        try:
            morador_atual = obj.morador
        except Morador.DoesNotExist:
            morador_atual = None

        if perfil_tipo == 'visitante':
            if morador_atual:
                morador_atual.user = None
                morador_atual.save(update_fields=['user'])
            return

        if morador_atual and (not morador_selecionado or morador_atual.pk != morador_selecionado.pk):
            morador_atual.user = None
            morador_atual.save(update_fields=['user'])

        if morador_selecionado:
            morador_selecionado.user = obj
            morador_selecionado.save(update_fields=['user'])

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .forms import CadastroForm
from .models import ConfiguracaoFinanceira, Morador, Mensalidade, NotaFiscal


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
admin.site.register(ConfiguracaoFinanceira)


# Re-registra o User com formulario que permite vincular Morador.
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    add_form = CadastroForm
    add_fieldsets = (
        (
            None,
            {
                'classes': ('wide',),
                'fields': ('username', 'email', 'morador', 'password1', 'password2'),
            },
        ),
    )

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        morador = form.cleaned_data.get('morador')
        if morador:
            morador.user = obj
            morador.save(update_fields=['user'])

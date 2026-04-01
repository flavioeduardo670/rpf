from django.contrib import admin
from .models import ConfiguracaoFinanceira, Morador, Mensalidade, NotaFiscal
from django.contrib.auth.models import User



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
        'data_aniversario',
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
                'data_aniversario',
                'funcoes',
                'ativo',
            )
        }),
        ('Permissões de Acesso', {
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



# Remove User padrão e oculta cadastro de usuários no admin
admin.site.unregister(User)


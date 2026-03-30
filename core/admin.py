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
        'ativo',
        'acesso_financeiro',
        'acesso_compras',
        'acesso_estoque',
        'acesso_manutencao'
    )

    list_filter = (
        'ativo',
        'acesso_financeiro',
        'acesso_compras',
        'acesso_estoque',
        'acesso_manutencao'
    )

    search_fields = ('nome', 'apelido', 'email')

    fieldsets = (
        ('Dados Pessoais', {
            'fields': ('ordem_hierarquia', 'nome', 'apelido', 'email', 'quarto', 'ativo')
        }),
        ('Permissões de Acesso', {
            'fields': (
                'acesso_financeiro',
                'acesso_compras',
                'acesso_estoque',
                'acesso_manutencao'
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



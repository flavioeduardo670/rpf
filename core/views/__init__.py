from .financeiro import editar_parcela, exportar_financeiro_csv, financeiro, pagar_nota, pagar_parcela
from .api import (
    api_compras,
    api_estoque,
    api_financeiro,
    api_financeiro_rateio,
    api_manutencao,
    api_moradores,
    api_rock,
    api_root,
    api_setores,
)
from .estoque import (
    almoxarifado,
    consumo_historico,
    editar_produto,
    exportar_consumo_csv,
    exportar_estoque_csv,
    registrar_consumo,
)
from .legacy import (
    cadastro,
    compras,
    editar_nota_compra,
    editar_os,
    gerenciar_acessos,
    home,
    lista_os,
    manutencao,
    moradores,
    perfil,
    rock,
    exportar_compras_csv,
    exportar_moradores_csv,
)

from .acessos import gerenciar_acessos
from .financeiro import editar_parcela, exportar_financeiro_csv, financeiro, pagar_nota, pagar_parcela
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
    calendario,
    compras,
    configurar_formularios,
    configurar_listas,
    editar_nota_compra,
    editar_os,
    home,
    lista_os,
    manutencao,
    exportar_compras_csv,
)
from .moradores import exportar_moradores_csv, moradores, perfil
from .rock import (
    comprar_rocks,
    editar_rock,
    exportar_ingressos_rock_pdf,
    ingressos_rock,
    lotes_rock,
    rock,
)
from .pix import webhook_pix

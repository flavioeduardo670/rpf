from .acessos import gerenciar_acessos
from .auth_cadastro import cadastro, calendario, home
from .financeiro import (
    compras,
    anexar_comprovante_pagamento,
    editar_nota_compra,
    editar_parcela,
    editar_rateio_parcela,
    exportar_compras_csv,
    exportar_financeiro_csv,
    financeiro,
    pagar_nota,
    pagar_parcela,
    ver_comprovante_pagamento,
)
from .estoque import (
    almoxarifado,
    consumo_historico,
    editar_produto,
    exportar_consumo_csv,
    exportar_estoque_csv,
    registrar_consumo,
)
from .legacy import configurar_formularios, configurar_listas
from .manutencao import editar_os, lista_os, manutencao
from .moradores import exportar_moradores_csv, moradores, perfil
from .pix import webhook_pix
from .rock import comprar_rocks, editar_rock, exportar_ingressos_rock_pdf, ingressos_rock, lotes_rock, rock
from .reunioes import adicionar_ata_reuniao, reunioes

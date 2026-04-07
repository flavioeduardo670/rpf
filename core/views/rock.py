"""Views do domínio Rock.

Neste estágio da migração, as implementações continuam em ``legacy`` e
são reexportadas aqui para separar a superfície pública por domínio.
"""

from .legacy import (  # noqa: F401
    comprar_rocks,
    editar_rock,
    exportar_ingressos_rock_pdf,
    ingressos_rock,
    lotes_rock,
    rock,
)

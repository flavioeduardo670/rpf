from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO

from django.template.loader import render_to_string
from xhtml2pdf import pisa

from core.models import AtaReuniao


@dataclass(frozen=True)
class Item5W2H:
    what: str
    why: str
    where: str
    when: str
    who: str
    how: str
    how_much: str


def _split_multilines(raw_text: str) -> list[str]:
    return [line.strip() for line in (raw_text or '').splitlines() if line.strip()]


def _parse_5w2h(raw_text: str) -> list[Item5W2H]:
    itens: list[Item5W2H] = []
    for line in _split_multilines(raw_text):
        colunas = [col.strip() for col in line.split('|')]
        if len(colunas) < 7:
            colunas.extend([''] * (7 - len(colunas)))
        itens.append(
            Item5W2H(
                what=colunas[0],
                why=colunas[1],
                where=colunas[2],
                when=colunas[3],
                who=colunas[4],
                how=colunas[5],
                how_much=colunas[6],
            )
        )
    return itens


def _render_html(ata: AtaReuniao) -> str:
    return render_to_string(
        'core/ata_pdf.html',
        {
            'ata': ata,
            'participantes': _split_multilines(ata.participantes_texto),
            'topicos': _split_multilines(ata.topicos_texto),
            'itens_5w2h': _parse_5w2h(ata.plano_acao_5w2h_texto),
        },
    )


def gerar_pdf_ata(ata: AtaReuniao) -> bytes:
    html = _render_html(ata)
    output = BytesIO()
    status = pisa.CreatePDF(src=html, dest=output, encoding='utf-8')
    if status.err:
        raise RuntimeError('Nao foi possivel converter a ata para PDF.')
    return output.getvalue()

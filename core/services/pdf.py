"""Geração de PDFs simples sem dependências externas.

O sistema monta PDFs "na mão" (operadores de texto + fontes Type1 padrão)
para não depender de bibliotecas como reportlab em produção. Este módulo
concentra essa lógica para que financeiro, rock e atas usem o mesmo código.
"""
from decimal import Decimal

A4_LARGURA = 595
A4_ALTURA = 842


def escapar_texto_pdf(valor):
    """Normaliza espaços e escapa os caracteres especiais de strings PDF."""
    texto = ' '.join(str(valor if valor is not None else '').split())
    texto = texto.replace('—', '-').replace('–', '-').replace('·', '-')
    return texto.replace('\\', '\\\\').replace('(', '\\(').replace(')', '\\)')


def quebrar_texto(texto, largura=90):
    """Quebra um texto em linhas de até ``largura`` caracteres."""
    palavras = str(texto or '').split()
    if not palavras:
        return ['']
    linhas = []
    linha_atual = ''
    for palavra in palavras:
        candidata = f"{linha_atual} {palavra}".strip()
        if len(candidata) <= largura:
            linha_atual = candidata
            continue
        if linha_atual:
            linhas.append(linha_atual)
        while len(palavra) > largura:
            linhas.append(palavra[:largura])
            palavra = palavra[largura:]
        linha_atual = palavra
    if linha_atual:
        linhas.append(linha_atual)
    return linhas


def montar_pdf_por_comandos(comandos_paginas, largura_pagina, altura_pagina):
    """Monta o binário do PDF a partir de uma lista de páginas de comandos.

    Cada página é uma lista de operadores de conteúdo PDF. As fontes /F1
    (Helvetica) e /F2 (Helvetica-Bold) ficam disponíveis em todas as páginas,
    com codificação WinAnsi para acentos do português.
    """
    objetos = [b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n"]
    kids = []
    fonte_regular_obj = 3 + (len(comandos_paginas) * 2)
    fonte_bold_obj = fonte_regular_obj + 1
    for indice, comandos_pagina in enumerate(comandos_paginas):
        pagina_obj = 3 + (indice * 2)
        conteudo_obj = pagina_obj + 1
        kids.append(f"{pagina_obj} 0 R")
        stream = '\n'.join(comandos_pagina).encode('cp1252', errors='replace')
        objetos.append(
            f"{pagina_obj} 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 {largura_pagina} {altura_pagina}] /Resources << /Font << /F1 {fonte_regular_obj} 0 R /F2 {fonte_bold_obj} 0 R >> >> /Contents {conteudo_obj} 0 R >> endobj\n".encode('latin-1')
        )
        objetos.append(
            f"{conteudo_obj} 0 obj << /Length {len(stream)} >> stream\n".encode('latin-1')
            + stream
            + b"\nendstream endobj\n"
        )
    objetos.insert(
        1,
        f"2 0 obj << /Type /Pages /Kids [{' '.join(kids)}] /Count {len(comandos_paginas)} >> endobj\n".encode('latin-1'),
    )
    objetos.append(f"{fonte_regular_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >> endobj\n".encode('latin-1'))
    objetos.append(f"{fonte_bold_obj} 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >> endobj\n".encode('latin-1'))

    pdf = b'%PDF-1.4\n'
    offsets = [0]
    for obj in objetos:
        offsets.append(len(pdf))
        pdf += obj
    xref_start = len(pdf)
    pdf += f"xref\n0 {len(offsets)}\n".encode('latin-1') + b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode('latin-1')
    pdf += (f"trailer << /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{xref_start}\n%%EOF").encode('latin-1')
    return pdf


def _comando_texto(texto, x, y, tamanho=10, fonte='F1'):
    return f"0.10 0.10 0.10 rg BT /{fonte} {tamanho} Tf 1 0 0 1 {Decimal(x):.2f} {Decimal(y):.2f} Tm ({escapar_texto_pdf(texto)}) Tj ET"


def gerar_pdf_texto(titulo, linhas, *, tamanho=10, largura_linha=90):
    """Gera um PDF A4 com título e linhas de texto, em quantas páginas forem
    necessárias. Linhas longas são quebradas; nada é descartado."""
    margem = 40
    altura_linha = tamanho + 5
    paginas = []
    comandos = []

    def nova_pagina():
        nonlocal comandos
        comandos = []
        paginas.append(comandos)
        comandos.append(_comando_texto(titulo, margem, A4_ALTURA - 50, 14, 'F2'))
        return A4_ALTURA - 50 - 26

    y = nova_pagina()
    for linha in linhas:
        for trecho in quebrar_texto(linha, largura_linha):
            if y < margem:
                y = nova_pagina()
            comandos.append(_comando_texto(trecho, margem, y, tamanho))
            y -= altura_linha

    total = len(paginas)
    if total > 1:
        for numero, pagina in enumerate(paginas, start=1):
            pagina.append(_comando_texto(f'Página {numero}/{total}', A4_LARGURA - margem - 60, 20, 8))

    return montar_pdf_por_comandos(paginas, A4_LARGURA, A4_ALTURA)

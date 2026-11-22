"""Leitura do XML oficial da NF-e / NFC-e (procNFe, NFe ou resNFe).

O XML é a fonte mais confiável: vem por e-mail do caixa (solução 3) ou da
Distribuição de DF-e da Receita com o certificado da república (solução 4).
"""
from __future__ import annotations

import re
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from defusedxml import ElementTree as ET

from .nfce import DadosNFCe, ItemNFCe, UF_POR_CODIGO, chave_acesso_valida

NS = '{http://www.portalfiscal.inf.br/nfe}'
TAMANHO_MAXIMO_XML = 2 * 1024 * 1024


class XMLNotaInvalido(ValueError):
    pass


def _texto(elemento, caminho: str) -> str:
    if elemento is None:
        return ''
    achado = elemento.find(caminho.replace('nfe:', NS))
    return (achado.text or '').strip() if achado is not None and achado.text else ''


def _decimal(texto: str) -> Decimal | None:
    try:
        return Decimal(texto) if texto else None
    except InvalidOperation:
        return None


def _data(texto: str) -> date | None:
    if not texto:
        return None
    try:
        return datetime.fromisoformat(texto).date()
    except ValueError:
        try:
            return date.fromisoformat(texto[:10])
        except ValueError:
            return None


def _raiz(conteudo: bytes | str):
    if isinstance(conteudo, str):
        conteudo = conteudo.encode('utf-8')
    if len(conteudo) > TAMANHO_MAXIMO_XML:
        raise XMLNotaInvalido('O arquivo XML é grande demais.')
    try:
        return ET.fromstring(conteudo)
    except Exception as exc:  # ParseError e bloqueios do defusedxml
        raise XMLNotaInvalido('Não consegui abrir o arquivo como XML de nota fiscal.') from exc


def _dados_base(chave: str) -> DadosNFCe:
    return DadosNFCe(
        chave_acesso=chave,
        uf=UF_POR_CODIGO.get(chave[:2], ''),
        cnpj_emitente=chave[6:20],
        modelo=chave[20:22],
        serie=str(int(chave[22:25])),
        numero=str(int(chave[25:34])),
    )


def ler_xml_nota(conteudo: bytes | str) -> DadosNFCe:
    """Aceita procNFe/nfeProc, NFe ou resNFe (resumo). Levanta XMLNotaInvalido."""
    raiz = _raiz(conteudo)

    if raiz.tag == f'{NS}resNFe':
        return _ler_resumo(raiz)

    inf = raiz.find(f'.//{NS}infNFe')
    if inf is None:
        raise XMLNotaInvalido('O XML não é de uma NF-e/NFC-e (faltou infNFe).')
    chave = re.sub(r'\D', '', inf.get('Id', ''))
    if not chave_acesso_valida(chave):
        chave_prot = _texto(raiz, './/nfe:protNFe/nfe:infProt/nfe:chNFe')
        chave = chave_prot if chave_acesso_valida(chave_prot) else ''
    if not chave:
        raise XMLNotaInvalido('O XML não tem uma chave de acesso válida.')

    dados = _dados_base(chave)
    emit = inf.find(f'{NS}emit')
    dados.cnpj_emitente = _texto(emit, 'nfe:CNPJ') or dados.cnpj_emitente
    dados.fornecedor = (_texto(emit, 'nfe:xFant') or _texto(emit, 'nfe:xNome'))[:100]
    ide = inf.find(f'{NS}ide')
    dados.data_emissao = _data(_texto(ide, 'nfe:dhEmi') or _texto(ide, 'nfe:dEmi'))
    dados.valor_total = _decimal(_texto(inf, 'nfe:total/nfe:ICMSTot/nfe:vNF'))

    for det in inf.findall(f'{NS}det'):
        prod = det.find(f'{NS}prod')
        descricao = _texto(prod, 'nfe:xProd')
        quantidade = _decimal(_texto(prod, 'nfe:qCom')) or Decimal('1')
        valor_total = _decimal(_texto(prod, 'nfe:vProd'))
        if not descricao or valor_total is None:
            continue
        desconto = _decimal(_texto(prod, 'nfe:vDesc')) or Decimal('0')
        valor_total = (valor_total - desconto).quantize(Decimal('0.01'))
        if quantidade == quantidade.to_integral_value():
            quantidade = quantidade.to_integral_value()
        valor_unitario = _decimal(_texto(prod, 'nfe:vUnCom'))
        if desconto or valor_unitario is None:
            valor_unitario = (valor_total / quantidade).quantize(Decimal('0.01')) if quantidade else valor_total
        dados.itens.append(ItemNFCe(
            descricao=descricao[:200],
            quantidade=quantidade,
            unidade=_texto(prod, 'nfe:uCom')[:10],
            valor_unitario=valor_unitario.quantize(Decimal('0.01')),
            valor_total=valor_total,
        ))

    if dados.valor_total is None and dados.itens:
        dados.valor_total = sum((item.valor_total for item in dados.itens), Decimal('0.00'))
    dados.consulta_sefaz_ok = True
    return dados


def _ler_resumo(raiz) -> DadosNFCe:
    """resNFe: só o resumo (sem itens), entregue pela Distribuição de DF-e
    antes da manifestação do destinatário."""
    chave = _texto(raiz, 'nfe:chNFe')
    if not chave_acesso_valida(chave):
        raise XMLNotaInvalido('O resumo da NF-e não tem chave de acesso válida.')
    dados = _dados_base(chave)
    dados.cnpj_emitente = _texto(raiz, 'nfe:CNPJ') or dados.cnpj_emitente
    dados.fornecedor = _texto(raiz, 'nfe:xNome')[:100]
    dados.data_emissao = _data(_texto(raiz, 'nfe:dhEmi'))
    dados.valor_total = _decimal(_texto(raiz, 'nfe:vNF'))
    dados.consulta_sefaz_ok = True
    return dados


def resumo_autorizado_de_compra(conteudo: bytes | str) -> bool:
    """resNFe de nota de saída do emitente (tpNF=1) e autorizada (cSitNFe=1):
    é uma compra feita pela república."""
    raiz = _raiz(conteudo)
    return _texto(raiz, 'nfe:tpNF') == '1' and _texto(raiz, 'nfe:cSitNFe') == '1'

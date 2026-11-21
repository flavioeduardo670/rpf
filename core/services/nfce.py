"""Leitura do QR Code de NFC-e (nota fiscal de consumidor) para o Compras.

O QR Code traz uma URL do portal da SEFAZ do estado com a chave de acesso de
44 dígitos. Da chave saem estado, mês/ano, CNPJ do emitente e número da nota;
nas versões offline/antigas do QR também vêm data e valor total. Os itens e o
nome da loja só existem na página pública da SEFAZ, que é consultada quando
possível (sem ela, a compra é registrada com o total).
"""
from __future__ import annotations

import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from urllib import error, parse, request

from bs4 import BeautifulSoup

logger = logging.getLogger('core.services.nfce')

TIMEOUT_CONSULTA = 12
TAMANHO_MAXIMO_PAGINA = 3 * 1024 * 1024
USER_AGENT = (
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
    '(KHTML, like Gecko) Chrome/124.0 Safari/537.36'
)

UF_POR_CODIGO = {
    '11': 'RO', '12': 'AC', '13': 'AM', '14': 'RR', '15': 'PA', '16': 'AP', '17': 'TO',
    '21': 'MA', '22': 'PI', '23': 'CE', '24': 'RN', '25': 'PB', '26': 'PE', '27': 'AL',
    '28': 'SE', '29': 'BA', '31': 'MG', '32': 'ES', '33': 'RJ', '35': 'SP', '41': 'PR',
    '42': 'SC', '43': 'RS', '50': 'MS', '51': 'MT', '52': 'GO', '53': 'DF',
}


class QRCodeNFCeInvalido(ValueError):
    pass


@dataclass
class ItemNFCe:
    descricao: str
    quantidade: Decimal
    unidade: str
    valor_unitario: Decimal
    valor_total: Decimal


@dataclass
class DadosNFCe:
    chave_acesso: str
    url_consulta: str = ''
    uf: str = ''
    cnpj_emitente: str = ''
    modelo: str = ''
    serie: str = ''
    numero: str = ''
    data_emissao: date | None = None
    valor_total: Decimal | None = None
    fornecedor: str = ''
    itens: list[ItemNFCe] = field(default_factory=list)
    consulta_sefaz_ok: bool = False
    aviso_consulta: str = ''

    def para_sessao(self) -> dict:
        """Versão serializável em JSON (sessão do Django)."""
        dados = asdict(self)
        dados['data_emissao'] = self.data_emissao.isoformat() if self.data_emissao else ''
        dados['valor_total'] = str(self.valor_total) if self.valor_total is not None else ''
        dados['itens'] = [
            {k: str(v) if isinstance(v, Decimal) else v for k, v in asdict(item).items()}
            for item in self.itens
        ]
        return dados

    @classmethod
    def da_sessao(cls, dados: dict) -> 'DadosNFCe':
        dados = dict(dados)
        dados['data_emissao'] = date.fromisoformat(dados['data_emissao']) if dados.get('data_emissao') else None
        dados['valor_total'] = Decimal(dados['valor_total']) if dados.get('valor_total') else None
        dados['itens'] = [
            ItemNFCe(
                descricao=item['descricao'],
                quantidade=Decimal(item['quantidade']),
                unidade=item.get('unidade', ''),
                valor_unitario=Decimal(item['valor_unitario']),
                valor_total=Decimal(item['valor_total']),
            )
            for item in dados.get('itens') or []
        ]
        return cls(**dados)


# ---------------------------------------------------------------------------
# Chave de acesso
# ---------------------------------------------------------------------------

def digito_verificador_chave(chave43: str) -> int:
    soma = 0
    peso = 2
    for digito in reversed(chave43):
        soma += int(digito) * peso
        peso = 2 if peso == 9 else peso + 1
    resto = soma % 11
    return 0 if resto in (0, 1) else 11 - resto


def chave_acesso_valida(chave: str) -> bool:
    return bool(re.fullmatch(r'\d{44}', chave or '')) and digito_verificador_chave(chave[:43]) == int(chave[43])


def formatar_cnpj(cnpj: str) -> str:
    if len(cnpj) != 14:
        return cnpj
    return f'{cnpj[:2]}.{cnpj[2:5]}.{cnpj[5:8]}/{cnpj[8:12]}-{cnpj[12:]}'


def _decimal_br(texto: str) -> Decimal | None:
    """'1.234,56' / '1234.56' / 'R$ 9,98' -> Decimal."""
    limpo = re.sub(r'[^\d,.\-]', '', texto or '')
    if not limpo:
        return None
    if ',' in limpo:
        limpo = limpo.replace('.', '').replace(',', '.')
    try:
        return Decimal(limpo)
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# QR Code
# ---------------------------------------------------------------------------

def interpretar_qrcode_nfce(conteudo: str) -> DadosNFCe:
    """Extrai o que dá para saber só pelo conteúdo do QR Code."""
    texto = (conteudo or '').strip()
    if not texto:
        raise QRCodeNFCeInvalido('O QR Code está vazio.')

    url_consulta = texto if re.match(r'^https?://', texto, re.IGNORECASE) else ''
    query = parse.parse_qs(parse.urlsplit(texto).query) if url_consulta else {}
    partes_p = (query.get('p') or [''])[0].split('|') if query.get('p') else []

    candidatos = []
    if partes_p:
        candidatos.append(partes_p[0])
    candidatos.extend(query.get('chNFe') or [])
    candidatos.extend(re.findall(r'(?<!\d)\d{44}(?!\d)', re.sub(r'\s', '', texto)))
    chave = next((re.sub(r'\D', '', c) for c in candidatos if chave_acesso_valida(re.sub(r'\D', '', c))), '')
    if not chave:
        raise QRCodeNFCeInvalido(
            'Não encontrei uma chave de acesso válida. Confira se é o QR Code de uma nota fiscal (NFC-e).'
        )

    modelo = chave[20:22]
    dados = DadosNFCe(
        chave_acesso=chave,
        url_consulta=url_consulta,
        uf=UF_POR_CODIGO.get(chave[:2], ''),
        cnpj_emitente=chave[6:20],
        modelo=modelo,
        serie=str(int(chave[22:25])),
        numero=str(int(chave[25:34])),
    )
    ano, mes = 2000 + int(chave[2:4]), int(chave[4:6])

    # QR v2/v3 em contingência (offline): chave|versão|ambiente|dia|valor|...
    if len(partes_p) >= 6 and re.fullmatch(r'\d{1,2}', partes_p[3] or '') and _decimal_br(partes_p[4]) is not None:
        dados.valor_total = _decimal_br(partes_p[4])
        try:
            dados.data_emissao = date(ano, mes, int(partes_p[3]))
        except ValueError:
            pass

    # QR v1 (antigo): ?chNFe=...&vNF=12.34&dhEmi=<hex>
    if query.get('vNF'):
        dados.valor_total = _decimal_br(query['vNF'][0])
    if query.get('dhEmi'):
        try:
            emissao = bytes.fromhex(query['dhEmi'][0]).decode('ascii')
            dados.data_emissao = datetime.fromisoformat(emissao[:10]).date()
        except ValueError:
            pass

    if dados.data_emissao is None and 1 <= mes <= 12:
        # A chave só tem mês/ano; o dia exato vem da SEFAZ ou é ajustado na tela.
        dados.data_emissao = date(ano, mes, 1)
    return dados


# ---------------------------------------------------------------------------
# Consulta pública na SEFAZ
# ---------------------------------------------------------------------------

def _host_permitido(url: str) -> bool:
    partes = parse.urlsplit(url)
    host = (partes.hostname or '').lower()
    return partes.scheme in {'http', 'https'} and host.endswith('.gov.br')


class _RedirecionamentoSeguro(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not _host_permitido(newurl):
            raise error.URLError('Redirecionamento para fora do portal da SEFAZ bloqueado.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _baixar_pagina(url: str) -> str:
    opener = request.build_opener(_RedirecionamentoSeguro)
    req = request.Request(url, headers={'User-Agent': USER_AGENT, 'Accept': 'text/html,application/xhtml+xml'})
    with opener.open(req, timeout=TIMEOUT_CONSULTA) as resposta:
        conteudo = resposta.read(TAMANHO_MAXIMO_PAGINA + 1)
        charset = resposta.headers.get_content_charset() or 'utf-8'
    if len(conteudo) > TAMANHO_MAXIMO_PAGINA:
        raise ValueError('Página da SEFAZ grande demais.')
    try:
        return conteudo.decode(charset)
    except (LookupError, UnicodeDecodeError):
        return conteudo.decode('latin-1')


def _texto(elemento) -> str:
    return re.sub(r'\s+', ' ', elemento.get_text(' ', strip=True)).strip() if elemento else ''


def _valor_apos_rotulo(elemento) -> str:
    """'Qtde.: 2' -> '2' (o rótulo fica num <strong> dentro do span)."""
    texto = _texto(elemento)
    return texto.split(':', 1)[1].strip() if ':' in texto else texto


def extrair_dados_pagina_sefaz(html: str) -> dict:
    """Lê o layout padrão da consulta pública de NFC-e (usado pela maioria dos
    estados, ex.: SP, PR, RS, BA, GO): tabela #tabResult com spans txtTit,
    Rqtd, RUN, RvlUnit e valor."""
    soup = BeautifulSoup(html, 'html.parser')
    resultado: dict = {'fornecedor': '', 'itens': [], 'valor_total': None, 'data_emissao': None}

    emitente = soup.select_one('#u20') or soup.select_one('.txtTopo')
    resultado['fornecedor'] = _texto(emitente)

    for linha in soup.select('#tabResult tr'):
        nome = linha.select_one('span.txtTit') or linha.select_one('.txtTit')
        descricao = _texto(nome)
        if not descricao:
            continue
        quantidade = _decimal_br(_valor_apos_rotulo(linha.select_one('.Rqtd'))) or Decimal('1')
        unidade = _valor_apos_rotulo(linha.select_one('.RUN'))
        valor_unitario = _decimal_br(_valor_apos_rotulo(linha.select_one('.RvlUnit')))
        valor_total = _decimal_br(_texto(linha.select_one('.valor')))
        if valor_total is None and valor_unitario is not None:
            valor_total = (valor_unitario * quantidade).quantize(Decimal('0.01'))
        if valor_unitario is None and valor_total is not None:
            valor_unitario = (valor_total / quantidade).quantize(Decimal('0.01')) if quantidade else valor_total
        if valor_total is None:
            continue
        resultado['itens'].append(ItemNFCe(
            descricao=descricao[:200],
            quantidade=quantidade,
            unidade=unidade[:10],
            valor_unitario=valor_unitario,
            valor_total=valor_total,
        ))

    total = None
    for linha in soup.select('#totalNota #linhaTotal, #totalNota .linhaShade, #linhaTotal'):
        rotulo = _texto(linha.select_one('label')).lower()
        if 'valor a pagar' in rotulo:
            total = _decimal_br(_texto(linha.select_one('.totalNumb')))
            break
    if total is None:
        destaque = soup.select_one('.totalNumb.txtMax')
        total = _decimal_br(_texto(destaque)) if destaque else None
    resultado['valor_total'] = total

    emissao = re.search(r'Emiss[ãa]o:?\s*(\d{2}/\d{2}/\d{4})', soup.get_text(' ', strip=True))
    if emissao:
        try:
            resultado['data_emissao'] = datetime.strptime(emissao.group(1), '%d/%m/%Y').date()
        except ValueError:
            pass
    return resultado


def consultar_nfce(dados: DadosNFCe) -> DadosNFCe:
    """Completa os dados do QR com a página da SEFAZ. Nunca levanta exceção:
    se a consulta falhar, devolve o que veio do QR com um aviso."""
    if not dados.url_consulta:
        dados.aviso_consulta = 'Sem o link do QR Code não dá para buscar os itens na SEFAZ; confira o valor.'
        return dados
    if not _host_permitido(dados.url_consulta):
        dados.aviso_consulta = 'O link do QR Code não é de um portal da SEFAZ (.gov.br); confira os dados.'
        return dados
    try:
        html = _baixar_pagina(dados.url_consulta)
        extraido = extrair_dados_pagina_sefaz(html)
    except (error.URLError, TimeoutError, ValueError, OSError) as exc:
        logger.warning('Consulta da NFC-e na SEFAZ falhou.', extra={'event': 'nfce.consulta.erro', 'uf': dados.uf, 'erro': str(exc)[:200]})
        dados.aviso_consulta = 'A SEFAZ não respondeu agora; a compra será registrada pelo valor total. Confira o valor.'
        return dados

    if extraido['fornecedor']:
        dados.fornecedor = extraido['fornecedor'][:100]
    if extraido['itens']:
        dados.itens = extraido['itens']
    if extraido['valor_total'] is not None:
        dados.valor_total = extraido['valor_total']
    elif dados.itens and dados.valor_total is None:
        dados.valor_total = sum((item.valor_total for item in dados.itens), Decimal('0.00'))
    if extraido['data_emissao']:
        dados.data_emissao = extraido['data_emissao']

    dados.consulta_sefaz_ok = bool(extraido['itens'] or extraido['valor_total'] is not None)
    if not dados.consulta_sefaz_ok:
        dados.aviso_consulta = (
            f'Não consegui ler os itens no portal da SEFAZ{" de " + dados.uf if dados.uf else ""}; '
            'confira o fornecedor e o valor antes de registrar.'
        )
    return dados

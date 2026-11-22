"""Importação automática de notas (sem tela de conferência).

Usada pelo e-mail com XML (solução 3) e pela Distribuição de DF-e com o
certificado da república (solução 4). As compras entram como pendentes,
categoria "geral", cobradas no aluguel, e com a origem na observação para
quem for conferir depois.
"""
from __future__ import annotations

import email
import imaplib
import logging
import os
from dataclasses import dataclass, field
from email.message import Message

from core.models import NotaFiscal

from .nfce import DadosNFCe, formatar_cnpj
from .nfe_xml import XMLNotaInvalido, ler_xml_nota

logger = logging.getLogger('core.services.nfe_importacao')

TAMANHO_MAXIMO_ANEXO = 2 * 1024 * 1024


def registrar_compra_automatica(dados: DadosNFCe, origem: str) -> list[NotaFiscal]:
    """Registra a compra com os padrões do Compras. Não duplica: se a chave já
    existe, devolve []."""
    from core.views.compras_nfce import _descricao_padrao, registrar_compra_nfce

    if not dados.chave_acesso or dados.valor_total is None or dados.valor_total <= 0:
        return []
    if NotaFiscal.objects.filter(chave_acesso=dados.chave_acesso).exists():
        return []
    cd = {
        'fornecedor': (dados.fornecedor or f'CNPJ {formatar_cnpj(dados.cnpj_emitente)}')[:100],
        'descricao': _descricao_padrao(dados)[:200],
        'data_emissao': dados.data_emissao,
        'valor_total': dados.valor_total,
        'modo': 'total',
        'categoria_compra': 'geral',
        'tipo_item': 'Bem de Consumo',
        'cobrar_no_aluguel': True,
        'status': 'pendente',
        'forma_pagamento': '',
    }
    notas = registrar_compra_nfce(dados, cd, origem=origem)
    logger.info('Compra importada automaticamente.', extra={
        'event': 'nfe.importacao.registrada', 'origem': origem, 'chave': dados.chave_acesso,
    })
    return notas


# ---------------------------------------------------------------------------
# Solução 3: caixa de e-mail que recebe o XML da nota
# ---------------------------------------------------------------------------

@dataclass
class ConfigEmailNotas:
    host: str
    usuario: str
    senha: str
    pasta: str = 'INBOX'
    porta: int = 993

    @classmethod
    def do_ambiente(cls) -> 'ConfigEmailNotas | None':
        host = os.getenv('NFE_EMAIL_IMAP_HOST', '').strip()
        usuario = os.getenv('NFE_EMAIL_USUARIO', '').strip()
        senha = os.getenv('NFE_EMAIL_SENHA', '')
        if not (host and usuario and senha):
            return None
        return cls(
            host=host,
            usuario=usuario,
            senha=senha,
            pasta=os.getenv('NFE_EMAIL_PASTA', 'INBOX').strip() or 'INBOX',
            porta=int(os.getenv('NFE_EMAIL_IMAP_PORTA', '993')),
        )


@dataclass
class ResultadoImportacao:
    lidas: int = 0
    registradas: int = 0
    repetidas: int = 0
    erros: list[str] = field(default_factory=list)


def anexos_xml(mensagem: Message) -> list[bytes]:
    anexos = []
    for parte in mensagem.walk():
        nome = (parte.get_filename() or '').lower()
        tipo = parte.get_content_type()
        if not (nome.endswith('.xml') or tipo in {'application/xml', 'text/xml'}):
            continue
        conteudo = parte.get_payload(decode=True) or b''
        if conteudo and len(conteudo) <= TAMANHO_MAXIMO_ANEXO:
            anexos.append(conteudo)
    return anexos


def importar_xml(conteudo: bytes, origem: str, resultado: ResultadoImportacao) -> None:
    resultado.lidas += 1
    try:
        dados = ler_xml_nota(conteudo)
    except XMLNotaInvalido as exc:
        resultado.erros.append(str(exc))
        return
    if registrar_compra_automatica(dados, origem):
        resultado.registradas += 1
    else:
        resultado.repetidas += 1


def importar_notas_do_email(config: ConfigEmailNotas, imap_cls=imaplib.IMAP4_SSL) -> ResultadoImportacao:
    """Lê os e-mails não lidos da pasta, importa os XML anexados e marca o
    e-mail como lido. E-mails sem XML também são marcados como lidos."""
    resultado = ResultadoImportacao()
    conexao = imap_cls(config.host, config.porta)
    try:
        conexao.login(config.usuario, config.senha)
        conexao.select(config.pasta)
        status, dados = conexao.search(None, 'UNSEEN')
        if status != 'OK':
            resultado.erros.append('Não consegui listar os e-mails.')
            return resultado
        for numero in (dados[0] or b'').split():
            status, partes = conexao.fetch(numero, '(RFC822)')
            if status != 'OK' or not partes or not isinstance(partes[0], tuple):
                continue
            mensagem = email.message_from_bytes(partes[0][1])
            for anexo in anexos_xml(mensagem):
                importar_xml(anexo, 'e-mail', resultado)
            conexao.store(numero, '+FLAGS', '\\Seen')
    finally:
        try:
            conexao.logout()
        except Exception:  # noqa: BLE001 - a conexão pode já ter caído
            pass
    return resultado

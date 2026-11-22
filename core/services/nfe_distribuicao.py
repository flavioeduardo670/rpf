"""Solução 4: NF-e emitidas para o CNPJ da república, direto da Receita.

Usa o web service nacional NFeDistribuicaoDFe com o certificado digital A1
da república (mTLS). Vale para NF-e (modelo 55) com o CNPJ da república como
destinatário; o cupom NFC-e (modelo 65) não entra na distribuição.

Sem a manifestação do destinatário, a Receita entrega só o resumo (resNFe:
loja, data e valor total); com a manifestação ("Ciência da operação"), entrega
o XML completo com os itens. Esta integração importa os dois.
"""
from __future__ import annotations

import base64
import gzip
import logging
import os
import re
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import timedelta

import requests
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.serialization import pkcs12
from defusedxml import ElementTree as ET
from django.utils import timezone

from core.models import ControleDistribuicaoNFe

from .nfe_importacao import ResultadoImportacao, registrar_compra_automatica
from .nfe_xml import NS, XMLNotaInvalido, ler_xml_nota, resumo_autorizado_de_compra

logger = logging.getLogger('core.services.nfe_distribuicao')

URL_PRODUCAO = 'https://www1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx'
URL_HOMOLOGACAO = 'https://hom1.nfe.fazenda.gov.br/NFeDistribuicaoDFe/NFeDistribuicaoDFe.asmx'
SOAP_ACTION = 'http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe/nfeDistDFeInteresse'
TIMEOUT = 30
ESPERA_SEM_NOVIDADE = timedelta(hours=1)
CODIGO_UF = {
    'RO': '11', 'AC': '12', 'AM': '13', 'RR': '14', 'PA': '15', 'AP': '16', 'TO': '17',
    'MA': '21', 'PI': '22', 'CE': '23', 'RN': '24', 'PB': '25', 'PE': '26', 'AL': '27',
    'SE': '28', 'BA': '29', 'MG': '31', 'ES': '32', 'RJ': '33', 'SP': '35', 'PR': '41',
    'SC': '42', 'RS': '43', 'MS': '50', 'MT': '51', 'GO': '52', 'DF': '53',
}


class DistribuicaoErro(RuntimeError):
    pass


@dataclass
class ConfigDistribuicao:
    cnpj: str
    pfx: bytes
    senha: str
    uf_autor: str = '31'
    ambiente: str = '1'

    @property
    def url(self) -> str:
        return URL_PRODUCAO if self.ambiente == '1' else URL_HOMOLOGACAO

    @classmethod
    def do_ambiente(cls) -> 'ConfigDistribuicao | None':
        cnpj = re.sub(r'\D', '', os.getenv('NFE_CNPJ', ''))
        senha = os.getenv('NFE_CERTIFICADO_SENHA', '')
        pfx = b''
        if os.getenv('NFE_CERTIFICADO_PFX_BASE64'):
            pfx = base64.b64decode(os.getenv('NFE_CERTIFICADO_PFX_BASE64'))
        elif os.getenv('NFE_CERTIFICADO_PFX_CAMINHO'):
            with open(os.getenv('NFE_CERTIFICADO_PFX_CAMINHO'), 'rb') as arquivo:
                pfx = arquivo.read()
        if len(cnpj) != 14 or not pfx:
            return None
        uf = os.getenv('NFE_UF', 'MG').strip().upper()
        return cls(
            cnpj=cnpj,
            pfx=pfx,
            senha=senha,
            uf_autor=CODIGO_UF.get(uf, uf if uf.isdigit() else '31'),
            ambiente='2' if os.getenv('NFE_AMBIENTE', '1').strip() == '2' else '1',
        )


@dataclass
class RespostaDistribuicao:
    status: str
    motivo: str
    ult_nsu: str
    max_nsu: str
    documentos: list[tuple[str, str, bytes]] = field(default_factory=list)  # (nsu, schema, xml)


def montar_envelope(config: ConfigDistribuicao, ult_nsu: str) -> str:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap12:Envelope xmlns:soap12="http://www.w3.org/2003/05/soap-envelope">'
        '<soap12:Body>'
        '<nfeDistDFeInteresse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe">'
        '<nfeDadosMsg>'
        '<distDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">'
        f'<tpAmb>{config.ambiente}</tpAmb>'
        f'<cUFAutor>{config.uf_autor}</cUFAutor>'
        f'<CNPJ>{config.cnpj}</CNPJ>'
        f'<distNSU><ultNSU>{ult_nsu.zfill(15)}</ultNSU></distNSU>'
        '</distDFeInt>'
        '</nfeDadosMsg>'
        '</nfeDistDFeInteresse>'
        '</soap12:Body>'
        '</soap12:Envelope>'
    )


def ler_resposta(conteudo: bytes | str) -> RespostaDistribuicao:
    if isinstance(conteudo, str):
        conteudo = conteudo.encode('utf-8')
    try:
        raiz = ET.fromstring(conteudo)
    except Exception as exc:
        raise DistribuicaoErro('Resposta da Receita não é um XML válido.') from exc
    ret = raiz.find(f'.//{NS}retDistDFeInt')
    if ret is None:
        raise DistribuicaoErro('Resposta da Receita sem retDistDFeInt.')

    def campo(nome):
        achado = ret.find(f'{NS}{nome}')
        return (achado.text or '').strip() if achado is not None and achado.text else ''

    resposta = RespostaDistribuicao(
        status=campo('cStat'),
        motivo=campo('xMotivo'),
        ult_nsu=campo('ultNSU') or '0',
        max_nsu=campo('maxNSU') or '0',
    )
    for doc in ret.findall(f'.//{NS}docZip'):
        try:
            xml = gzip.decompress(base64.b64decode(doc.text or ''))
        except (OSError, ValueError):
            continue
        resposta.documentos.append((doc.get('NSU', ''), doc.get('schema', ''), xml))
    return resposta


@contextmanager
def _certificado_pem(config: ConfigDistribuicao):
    """O requests precisa do certificado e da chave em arquivos PEM."""
    try:
        chave, certificado, _ = pkcs12.load_key_and_certificates(
            config.pfx, config.senha.encode('utf-8') if config.senha else None
        )
    except ValueError as exc:
        raise DistribuicaoErro('Não consegui abrir o certificado A1 (confira o arquivo e a senha).') from exc
    if chave is None or certificado is None:
        raise DistribuicaoErro('O certificado A1 não tem chave privada.')
    arquivos = []
    try:
        for conteudo in (
            certificado.public_bytes(serialization.Encoding.PEM),
            chave.private_bytes(
                serialization.Encoding.PEM,
                serialization.PrivateFormat.PKCS8,
                serialization.NoEncryption(),
            ),
        ):
            arquivo = tempfile.NamedTemporaryFile(delete=False, suffix='.pem')
            arquivo.write(conteudo)
            arquivo.close()
            arquivos.append(arquivo.name)
        yield tuple(arquivos)
    finally:
        for caminho in arquivos:
            try:
                os.remove(caminho)
            except OSError:
                pass


def consultar_lote(config: ConfigDistribuicao, ult_nsu: str, post=requests.post) -> RespostaDistribuicao:
    with _certificado_pem(config) as certificado:
        try:
            resposta = post(
                config.url,
                data=montar_envelope(config, ult_nsu).encode('utf-8'),
                headers={'Content-Type': f'application/soap+xml; charset=utf-8; action="{SOAP_ACTION}"'},
                cert=certificado,
                timeout=TIMEOUT,
            )
        except requests.RequestException as exc:
            raise DistribuicaoErro(f'A Receita não respondeu: {exc}') from exc
    if resposta.status_code != 200:
        raise DistribuicaoErro(f'A Receita respondeu HTTP {resposta.status_code}.')
    return ler_resposta(resposta.content)


def _importar_documento(schema: str, xml: bytes, resultado: ResultadoImportacao) -> None:
    if not (schema.startswith('resNFe') or schema.startswith('procNFe')):
        return  # eventos (cancelamento, carta de correção...) não viram compra
    resultado.lidas += 1
    try:
        if schema.startswith('resNFe') and not resumo_autorizado_de_compra(xml):
            return
        dados = ler_xml_nota(xml)
    except XMLNotaInvalido as exc:
        resultado.erros.append(str(exc))
        return
    if registrar_compra_automatica(dados, 'Receita (certificado A1)'):
        resultado.registradas += 1
    else:
        resultado.repetidas += 1


def importar_distribuicao(config: ConfigDistribuicao, max_lotes: int = 10, post=requests.post) -> ResultadoImportacao:
    """Lê os lotes novos desde o último NSU. Respeita a espera de 1 hora que a
    Receita exige quando não há documentos novos."""
    resultado = ResultadoImportacao()
    controle, _ = ControleDistribuicaoNFe.objects.get_or_create(cnpj=config.cnpj)
    agora = timezone.now()
    if controle.proxima_consulta_apos and controle.proxima_consulta_apos > agora:
        resultado.erros.append(
            f'Aguardando a Receita liberar nova consulta após {timezone.localtime(controle.proxima_consulta_apos):%d/%m %H:%M}.'
        )
        return resultado

    for _ in range(max_lotes):
        resposta = consultar_lote(config, controle.ult_nsu, post=post)
        controle.ultima_consulta = timezone.now()
        controle.ultimo_status = f'{resposta.status} - {resposta.motivo}'[:255]
        if resposta.status == '138':
            for _nsu, schema, xml in resposta.documentos:
                _importar_documento(schema, xml, resultado)
            controle.ult_nsu = resposta.ult_nsu.zfill(15)
            controle.max_nsu = resposta.max_nsu.zfill(15)
            controle.proxima_consulta_apos = None
            controle.save()
            if int(resposta.ult_nsu or 0) >= int(resposta.max_nsu or 0):
                break
            continue
        # 137 = nenhum documento novo; demais = erro/consumo indevido: espera 1h.
        controle.proxima_consulta_apos = timezone.now() + ESPERA_SEM_NOVIDADE
        if resposta.status != '137':
            resultado.erros.append(controle.ultimo_status)
            logger.warning('Distribuição de DF-e recusou a consulta.', extra={
                'event': 'nfe.distribuicao.recusa', 'status': resposta.status, 'motivo': resposta.motivo[:200],
            })
        controle.save()
        break
    return resultado

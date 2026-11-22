"""Solução 1: ler a nota fiscal pela foto do cupom impresso (API do Claude).

O cupom traz loja, CNPJ, itens, total, data e a chave de acesso; nada disso
depende do portal da SEFAZ. A leitura volta para a mesma tela de conferência,
então um erro de leitura é corrigido antes de registrar.

Configuração: ANTHROPIC_API_KEY (obrigatória) e NFCE_FOTO_MODELO (opcional,
padrão claude-opus-5-5).
"""
from __future__ import annotations

import base64
import io
import logging
import os
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from .nfce import DadosNFCe, ItemNFCe, UF_POR_CODIGO, chave_acesso_valida, formatar_cnpj

logger = logging.getLogger('core.services.nfce_foto')

MODELO_PADRAO = 'claude-opus-5-5'
TAMANHO_MAXIMO_FOTO = 15 * 1024 * 1024
LADO_MAXIMO = 2000

INSTRUCOES = (
    'Você lê fotos de cupons fiscais brasileiros (NFC-e / DANFE NFC-e / NF-e) para um sistema de '
    'compras de uma república estudantil. Transcreva só o que está impresso na nota, sem inventar. '
    'Valores em reais como números decimais com ponto (ex.: 12.5). Quantidade como número '
    '(ex.: 1.235 para 1,235 kg). Data no formato AAAA-MM-DD. Chave de acesso só com os 44 dígitos, '
    'sem espaços; se não estiver legível, deixe vazia. Para cada item, valor_total é o valor da '
    'linha já com desconto do item, se houver. valor_pago é o "Valor a pagar"/"Valor pago" da nota. '
    'Se a imagem não for uma nota fiscal, retorne eh_nota_fiscal=false e o resto vazio.'
)


class ItemFoto(BaseModel):
    descricao: str
    quantidade: float = Field(description='Quantidade do item')
    unidade: str = Field(description='UN, KG, L, etc.')
    valor_unitario: float
    valor_total: float


class NotaFoto(BaseModel):
    eh_nota_fiscal: bool
    loja: str = Field(description='Nome da loja (nome fantasia ou razão social)')
    cnpj: str = Field(description='CNPJ do emitente, só dígitos')
    data_emissao: str = Field(description='AAAA-MM-DD ou vazio')
    chave_acesso: str = Field(description='44 dígitos ou vazio')
    numero_nota: str
    valor_pago: float | None
    itens: list[ItemFoto]


class FotoNotaInvalida(ValueError):
    pass


def leitura_por_foto_configurada() -> bool:
    return bool(os.getenv('ANTHROPIC_API_KEY', '').strip())


def preparar_imagem(conteudo: bytes) -> tuple[str, str]:
    """Corrige a rotação do celular, reduz para no máximo 2000 px e devolve
    (base64, media_type) em JPEG."""
    if len(conteudo) > TAMANHO_MAXIMO_FOTO:
        raise FotoNotaInvalida('A foto é grande demais (máximo 15 MB).')
    try:
        imagem = Image.open(io.BytesIO(conteudo))
        imagem = ImageOps.exif_transpose(imagem)
    except (UnidentifiedImageError, OSError) as exc:
        raise FotoNotaInvalida('Não consegui abrir essa imagem. Envie uma foto JPG ou PNG.') from exc
    imagem = imagem.convert('RGB')
    imagem.thumbnail((LADO_MAXIMO, LADO_MAXIMO))
    saida = io.BytesIO()
    imagem.save(saida, format='JPEG', quality=88)
    return base64.standard_b64encode(saida.getvalue()).decode('ascii'), 'image/jpeg'


def _cliente():
    import anthropic

    return anthropic.Anthropic()


def extrair_nota_da_foto(conteudo: bytes, cliente=None) -> NotaFoto:
    import anthropic

    if not leitura_por_foto_configurada() and cliente is None:
        raise FotoNotaInvalida('A leitura por foto não está configurada (falta ANTHROPIC_API_KEY no servidor).')
    dados_imagem, media_type = preparar_imagem(conteudo)
    cliente = cliente or _cliente()
    try:
        resposta = cliente.beta.messages.parse(
            model=os.getenv('NFCE_FOTO_MODELO', MODELO_PADRAO).strip() or MODELO_PADRAO,
            max_tokens=16000,
            betas=['server-side-fallback-2026-07-01'],
            fallbacks='default',
            output_config={'effort': 'low'},
            system=INSTRUCOES,
            messages=[{
                'role': 'user',
                'content': [
                    {'type': 'image', 'source': {'type': 'base64', 'media_type': media_type, 'data': dados_imagem}},
                    {'type': 'text', 'text': 'Leia esta nota fiscal.'},
                ],
            }],
            output_format=NotaFoto,
        )
    except anthropic.RateLimitError as exc:
        raise FotoNotaInvalida('Muitas leituras seguidas; tente de novo em um minuto.') from exc
    except (anthropic.APIConnectionError, anthropic.APIStatusError) as exc:
        logger.warning('Leitura da foto da nota falhou.', extra={'event': 'nfce.foto.erro', 'erro': str(exc)[:200]})
        raise FotoNotaInvalida('O serviço de leitura da foto não respondeu agora. Tente de novo.') from exc

    if resposta.stop_reason == 'refusal' or resposta.parsed_output is None:
        raise FotoNotaInvalida('Não consegui ler essa foto. Tente outra, com a nota inteira e bem iluminada.')
    return resposta.parsed_output


def _decimal(valor) -> Decimal | None:
    if valor is None:
        return None
    try:
        return Decimal(str(valor)).quantize(Decimal('0.01'))
    except InvalidOperation:
        return None


def nota_foto_para_dados(nota: NotaFoto, base: DadosNFCe | None = None) -> DadosNFCe:
    """Converte a leitura em DadosNFCe. Com `base` (leitura do QR Code), só
    completa itens/valores e confere se é a mesma loja."""
    if not nota.eh_nota_fiscal:
        raise FotoNotaInvalida('A foto não parece ser de uma nota fiscal.')
    cnpj = re.sub(r'\D', '', nota.cnpj or '')
    chave = re.sub(r'\D', '', nota.chave_acesso or '')
    if base is not None:
        if cnpj and len(cnpj) == 14 and base.cnpj_emitente and cnpj != base.cnpj_emitente:
            raise FotoNotaInvalida(
                f'A foto é de outra loja (CNPJ {formatar_cnpj(cnpj)}). Fotografe a nota deste QR Code.'
            )
        dados = base
    elif chave_acesso_valida(chave):
        dados = DadosNFCe(
            chave_acesso=chave,
            uf=UF_POR_CODIGO.get(chave[:2], ''),
            cnpj_emitente=chave[6:20],
            modelo=chave[20:22],
            serie=str(int(chave[22:25])),
            numero=str(int(chave[25:34])),
        )
    else:
        dados = DadosNFCe(chave_acesso='', cnpj_emitente=cnpj if len(cnpj) == 14 else '', numero=(nota.numero_nota or '').strip()[:20])

    itens = []
    for item in nota.itens:
        valor_total = _decimal(item.valor_total)
        if not item.descricao.strip() or valor_total is None:
            continue
        quantidade = Decimal(str(item.quantidade or 1))
        if quantidade == quantidade.to_integral_value():
            quantidade = quantidade.to_integral_value()
        itens.append(ItemNFCe(
            descricao=item.descricao.strip()[:200],
            quantidade=quantidade,
            unidade=(item.unidade or '').strip()[:10],
            valor_unitario=_decimal(item.valor_unitario) or valor_total,
            valor_total=valor_total,
        ))
    if itens:
        dados.itens = itens
    if nota.loja.strip():
        dados.fornecedor = nota.loja.strip()[:100]
    valor = _decimal(nota.valor_pago)
    if valor is not None and valor > 0:
        dados.valor_total = valor
    elif itens:
        dados.valor_total = sum((item.valor_total for item in itens), Decimal('0.00'))
    try:
        if nota.data_emissao:
            dados.data_emissao = date.fromisoformat(nota.data_emissao[:10])
    except ValueError:
        pass
    dados.consulta_sefaz_ok = True
    dados.sefaz_pede_verificacao = False
    dados.aviso_consulta = '' if dados.chave_acesso else (
        'Lido pela foto, sem a chave de acesso: o sistema não consegue avisar se esta nota já foi registrada.'
    )
    return dados

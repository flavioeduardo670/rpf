"""Vocabulário de cada cliente.

O sistema nasceu numa república, então as telas falavam em "morador",
"aluguel", "rock", "casa" e "quarto". Cada segmento tem os seus termos (um bar
tem colaboradores e eventos; uma fazenda tem talhões), e cada organização pode
ajustar qualquer um deles no Admin (campo ``termos``).

Uso nos templates (via context processor ``termos``)::

    {{ termos.membros }}     -> moradores
    {{ termos.Membros }}     -> Moradores   (inicial maiúscula)
    {{ termos.do_local }}    -> da casa
    {{ termos.no_local }}    -> na casa
    {{ termos.os_eventos }}  -> os rocks

No Python: ``'{Membros} e {eventos}'.format_map(termos)``.
"""
from collections.abc import Mapping

# Chaves do vocabulário: chave -> (singular, plural, gênero 'm'/'f').
CHAVES = ('membro', 'local', 'cobranca', 'evento', 'unidade')

# Plural de cada chave como aparece nos templates ({{ termos.membros }}).
PLURAIS = {'membros': 'membro', 'locais': 'local', 'cobrancas': 'cobranca', 'eventos': 'evento', 'unidades': 'unidade'}

PRESETS = {
    'moradia': {
        'membro': ('morador', 'moradores', 'm'),
        'local': ('casa', 'casas', 'f'),
        'cobranca': ('aluguel', 'aluguéis', 'm'),
        'evento': ('rock', 'rocks', 'm'),
        'unidade': ('quarto', 'quartos', 'm'),
    },
    'bar': {
        'membro': ('colaborador', 'colaboradores', 'm'),
        'local': ('bar', 'bares', 'm'),
        'cobranca': ('mensalidade', 'mensalidades', 'f'),
        'evento': ('evento', 'eventos', 'm'),
        'unidade': ('setor', 'setores', 'm'),
    },
    'mercado': {
        'membro': ('colaborador', 'colaboradores', 'm'),
        'local': ('loja', 'lojas', 'f'),
        'cobranca': ('mensalidade', 'mensalidades', 'f'),
        'evento': ('evento', 'eventos', 'm'),
        'unidade': ('setor', 'setores', 'm'),
    },
    'agro': {
        'membro': ('colaborador', 'colaboradores', 'm'),
        'local': ('propriedade', 'propriedades', 'f'),
        'cobranca': ('mensalidade', 'mensalidades', 'f'),
        'evento': ('evento', 'eventos', 'm'),
        'unidade': ('talhão', 'talhões', 'm'),
    },
    'saude': {
        'membro': ('colaborador', 'colaboradores', 'm'),
        'local': ('unidade', 'unidades', 'f'),
        'cobranca': ('mensalidade', 'mensalidades', 'f'),
        'evento': ('evento', 'eventos', 'm'),
        'unidade': ('setor', 'setores', 'm'),
    },
    'outro': {
        'membro': ('membro', 'membros', 'm'),
        'local': ('organização', 'organizações', 'f'),
        'cobranca': ('mensalidade', 'mensalidades', 'f'),
        'evento': ('evento', 'eventos', 'm'),
        'unidade': ('unidade', 'unidades', 'f'),
    },
}

# Contrações: prefixo -> (masc. singular, fem. singular, masc. plural, fem. plural)
ARTIGOS = {
    'o': ('o', 'a', 'os', 'as'),
    'um': ('um', 'uma', 'uns', 'umas'),
    'do': ('do', 'da', 'dos', 'das'),
    'no': ('no', 'na', 'nos', 'nas'),
    'ao': ('ao', 'à', 'aos', 'às'),
    'pelo': ('pelo', 'pela', 'pelos', 'pelas'),
}
# Formas que aparecem nas chaves para cada prefixo (ex.: "dos_membros", "das_..." não é usado).
PREFIXOS_PLURAL = {'os': 'o', 'uns': 'um', 'dos': 'do', 'nos': 'no', 'aos': 'ao', 'pelos': 'pelo'}


def validar_termos(termos):
    """Erros de um dicionário de ajustes (campo Organizacao.termos)."""
    erros = []
    if not isinstance(termos, dict):
        return ['Use um objeto JSON, por exemplo {"membro": ["sócio", "sócios", "m"]}.']
    for chave, valor in termos.items():
        if chave not in CHAVES:
            erros.append(f'"{chave}" não é um termo conhecido (use: {", ".join(CHAVES)}).')
        elif not (isinstance(valor, (list, tuple)) and len(valor) == 3 and valor[2] in ('m', 'f')
                  and all(isinstance(v, str) and v.strip() for v in valor[:2])):
            erros.append(f'"{chave}" deve ser ["singular", "plural", "m" ou "f"].')
    return erros


class Termos(Mapping):
    """Vocabulário pronto para templates e ``str.format_map``."""

    def __init__(self, segmento='outro', ajustes=None):
        base = dict(PRESETS.get(segmento) or PRESETS['outro'])
        if ajustes and not validar_termos(ajustes):
            base.update({chave: tuple(valor) for chave, valor in ajustes.items()})
        self._termos = base

    def _resolver(self, chave):
        prefixo, _, nome = chave.partition('_') if '_' in chave else ('', '', chave)
        plural = False
        if nome in PLURAIS:
            nome, plural = PLURAIS[nome], True
        if nome not in self._termos:
            raise KeyError(chave)
        singular, plural_txt, genero = self._termos[nome]
        palavra = plural_txt if plural else singular
        if not prefixo:
            return palavra
        if plural:
            prefixo = PREFIXOS_PLURAL.get(prefixo, prefixo)
        if prefixo not in ARTIGOS:
            raise KeyError(chave)
        masc_s, fem_s, masc_p, fem_p = ARTIGOS[prefixo]
        artigo = (masc_p if genero == 'm' else fem_p) if plural else (masc_s if genero == 'm' else fem_s)
        return f'{artigo} {palavra}'

    def __getitem__(self, chave):
        texto = self._resolver(chave[0].lower() + chave[1:])
        return texto[0].upper() + texto[1:] if chave[0].isupper() else texto

    def __iter__(self):
        return iter(list(self._termos) + list(PLURAIS))

    def __len__(self):
        return len(self._termos) + len(PLURAIS)

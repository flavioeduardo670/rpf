#!/usr/bin/env python3
"""Gera os SVGs do boneco da República Portão dos Fundos.

O boneco é o do logo oficial (pictograma de saída de emergência com capelo,
correndo para a porta com o chopp). Ele é desenhado por um esqueleto
articulado (esqueleto.py), e cada seção tem uma cena própria (cenas.py).

Uso:  python3 scripts/boneco/gerar_boneco.py
Saída: core/static/core/boneco/
  icone-<secao>-{preto,branco}.svg   boneco correndo com o objeto (menu, atalhos)
  acao-<secao>-{preto,branco}.svg    a ação animada da seção (cabeçalho)
  corrida-<secao>.svg                transição: corre e entra pela porta
  porta-abrindo.svg                  chegada na página nova
  marca-{preto,branco}.svg           logo (porta + boneco com chopp)
"""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import cenas  # noqa: E402
from esqueleto import f  # noqa: E402
import poses as P  # noqa: E402

RAIZ = pathlib.Path(__file__).resolve().parents[2]
SAIDA = RAIZ / 'core' / 'static' / 'core' / 'boneco'

CORES = {'preto': ('#000', '#fff'), 'branco': ('#fff', '#000')}
VB_CENA = '150 96 610 516'      # enquadramento comum das ações (mesma escala em todas)
VB_ICONE = '200 92 500 534'     # enquadramento comum dos ícones correndo

PORTA = dict(x=120, y=197, w=188, h=406)
VAO = [(130, 212), (213, 250), (213, 550), (130, 588)]


def _svg(viewbox, corpo, estilo='', titulo=''):
    t = f'<title>{titulo}</title>' if titulo else ''
    st = f'<style>{estilo}</style>' if estilo else ''
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{viewbox}" role="img">{t}{st}\n{corpo}\n</svg>\n')


def _porta(cor_batente, cor_vao, extra=''):
    pts = ' '.join(f'{x},{y}' for x, y in VAO)
    return (f'<rect x="{PORTA["x"]}" y="{PORTA["y"]}" width="{PORTA["w"]}" height="{PORTA["h"]}" rx="9" fill="{cor_batente}"/>'
            f'<polygon points="{pts}" fill="{cor_vao}" stroke="{cor_vao}" stroke-width="6" stroke-linejoin="round"/>{extra}')


def _quadros(n, dur, iteracoes='infinite', prefixo='q'):
    """CSS de animação quadro a quadro (cada quadro aparece 1/n do ciclo)."""
    css = [f'.{prefixo}{{opacity:0}}']
    for i in range(n):
        a, b = 100 * i / n, 100 * (i + 1) / n
        if i == 0:
            kf = f'0%,{b - 0.01:.2f}%{{opacity:1}}{b:.2f}%,100%{{opacity:0}}'
        else:
            kf = f'0%,{a - 0.01:.2f}%{{opacity:0}}{a:.2f}%,{b - 0.01:.2f}%{{opacity:1}}{b:.2f}%,100%{{opacity:0}}'
        css.append(f'@keyframes {prefixo}{i}{{{kf}}}.{prefixo}{i}{{animation:{prefixo}{i} {dur}s linear {iteracoes}}}')
    return ''.join(css)


def icones(nome):
    for tom, (cor, fundo) in CORES.items():
        corpo, _ = cenas.cena(nome, cor, fundo, 'corrida', 0)
        (SAIDA / f'icone-{nome}-{tom}.svg').write_text(_svg(VB_ICONE, corpo))


def acao(nome):
    corrida_no_lugar = nome in ('inicio', 'compras')
    n = 8 if corrida_no_lugar else 4
    dur = 0.64 if corrida_no_lugar else 0.62
    voltas = 3
    for tom, (cor, fundo) in CORES.items():
        modo = 'corrida' if corrida_no_lugar else 'acao'
        grupos = ''.join(f'<g class="q q{i}">{cenas.cena(nome, cor, fundo, modo, i)[0]}</g>' for i in range(n))
        final = cenas.cena(nome, cor, fundo, 'pose')[0]
        estilo = (_quadros(n, dur, voltas)
                  + f'.fim{{opacity:0;animation:fim {dur * voltas:.2f}s linear forwards}}'
                  + '@keyframes fim{0%,99.9%{opacity:0}100%{opacity:1}}'
                  + '@media (prefers-reduced-motion: reduce){.q{display:none}.fim{opacity:1;animation:none}}')
        corpo = grupos + f'<g class="fim">{final}</g>'
        (SAIDA / f'acao-{nome}-{tom}.svg').write_text(_svg(VB_CENA, corpo, estilo))


def corrida(nome):
    """Transição: o boneco (branco) corre da direita e entra pela porta, que se fecha."""
    cor, fundo = '#fff', '#000'
    dur = 0.88
    grupos = ''.join(f'<g class="q q{i}">{cenas.cena(nome, cor, fundo, "corrida", i)[0]}</g>' for i in range(8))
    vao = ' '.join(f'{x},{y}' for x, y in VAO)
    estilo = (_quadros(8, 0.56)
              + f'.anda{{animation:anda {dur}s linear forwards}}'
              + '@keyframes anda{0%{transform:translateX(640px);opacity:1}70%{opacity:1}'
                '84%{transform:translateX(-300px);opacity:0}100%{transform:translateX(-300px);opacity:0}}'
              + f'.fecha{{transform-box:fill-box;transform-origin:100% 50%;transform:scaleX(0);animation:fecha {dur}s linear forwards}}'
              + '@keyframes fecha{0%,76%{transform:scaleX(0)}94%,100%{transform:scaleX(1)}}')
    corpo = (_porta(cor, fundo)
             + '<defs><clipPath id="entra"><rect x="308" y="0" width="2000" height="1000"/>'
             + f'<polygon points="{vao}"/></clipPath></defs>'
             + f'<g clip-path="url(#entra)"><g class="anda">{grupos}</g></g>'
             + f'<polygon class="fecha" points="{vao}" fill="{cor}" stroke="{cor}" stroke-width="6" stroke-linejoin="round"/>')
    (SAIDA / f'corrida-{nome}.svg').write_text(_svg('70 130 1000 500', corpo, estilo))


def porta_abrindo():
    vao = ' '.join(f'{x},{y}' for x, y in VAO)
    estilo = ('.abre{transform-box:fill-box;transform-origin:100% 50%;animation:abre .3s .05s ease-in forwards}'
              '@keyframes abre{to{transform:scaleX(0)}}')
    corpo = _porta('#fff', '#000') + f'<polygon class="abre" points="{vao}" fill="#fff" stroke="#fff" stroke-width="6" stroke-linejoin="round"/>'
    (SAIDA / 'porta-abrindo.svg').write_text(_svg('70 130 1000 500', corpo, estilo))


def marca():
    for tom, (cor, fundo) in CORES.items():
        boneco, _ = cenas.cena('inicio', cor, fundo, 'pose')
        corpo = _porta(cor, fundo) + boneco
        (SAIDA / f'marca-{tom}.svg').write_text(_svg('104 160 590 452', corpo, titulo='República Portão dos Fundos'))
    # favicon: quadrado preto com a marca branca
    boneco, _ = cenas.cena('inicio', '#fff', '#000', 'pose')
    fav = (f'<rect x="80" y="90" width="640" height="640" rx="110" fill="#000"/>'
           f'<g transform="translate(36 72)">{_porta("#fff", "#000")}{boneco}</g>')
    (RAIZ / 'core' / 'static' / 'core' / 'brand' / 'favicon.svg').write_text(_svg('80 90 640 640', fav, titulo='RPF'))


def roleta():
    """Ilustrações padrão da roleta da página inicial (1600x640)."""
    pasta = RAIZ / 'core' / 'static' / 'core' / 'roleta'
    pasta.mkdir(parents=True, exist_ok=True)
    ouro = P.OURO
    import random
    random.seed(7)

    # 1) A casa à noite: o boneco entra pela porta dos fundos com o chopp
    estrelas = ''.join(
        f'<circle cx="{random.randint(560, 1580)}" cy="{random.randint(20, 230)}" r="{random.choice([1.5, 2, 2.5, 3])}" fill="#fff" opacity="{random.choice([.5, .7, 1])}"/>'
        for _ in range(46))
    boneco, _ = cenas.cena('inicio', '#fff', '#000', 'pose')
    porta = _porta('#fff', ouro)
    casa = f'''<rect width="1600" height="640" fill="#000"/>{estrelas}
<circle cx="1460" cy="110" r="46" fill="{ouro}"/><circle cx="1482" cy="92" r="40" fill="#000"/>
<path d="M760 262 L1080 80 L1400 262" fill="none" stroke="#fff" stroke-width="12"/>
<rect x="790" y="262" width="580" height="338" fill="none" stroke="#fff" stroke-width="12"/>
<g fill="{ouro}"><rect x="830" y="300" width="90" height="70"/><rect x="1240" y="300" width="90" height="70"/><rect x="1240" y="410" width="90" height="70" opacity=".4"/></g>
<path d="M875 300v70M830 335h90M1285 300v70M1240 335h90M1285 410v70M1240 445h90" stroke="#000" stroke-width="6"/>
<g transform="translate(838 315) scale(.47)">{porta}{boneco}</g>
<path d="M0 600H1600" stroke="#fff" stroke-width="6"/>'''
    (pasta / 'casa.svg').write_text(_svg('0 0 1600 640', casa).replace('role="img"', 'preserveAspectRatio="xMidYMid slice"'))

    # 2) Rock: brinde de chopp e o boneco virando a caneca
    def caneca_grande(x, y, rot, espelho=1):
        return f'<g transform="translate({x} {y}) rotate({rot}) scale({3.2 * espelho} 3.2)">{P.caneca(0, 0, 0, 1)}</g>'
    bebendo, _ = cenas.cena('rock', '#000', ouro, 'pose')
    rock = (f'<rect width="1600" height="640" fill="{ouro}"/>'
            + caneca_grande(840, 330, 16, -1) + caneca_grande(1060, 330, -16)
            + ''.join(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#fff"/>' for x, y, r in [(950, 150, 12), (976, 118, 8), (922, 120, 7), (1000, 140, 6)])
            + '<g fill="#000"><path d="M680 130v86a26 22 0 1 1-12-18V130l70-18v70a26 22 0 1 1-12-18v-58z"/></g>'
            + f'<g transform="translate(990 84) scale(.92)">{bebendo}</g>')
    (pasta / 'rock.svg').write_text(_svg('0 0 1600 640', rock).replace('role="img"', 'preserveAspectRatio="xMidYMid slice"'))

    # 3) Agenda: calendário e o boneco escrevendo a ata
    escrevendo, _ = cenas.cena('reunioes', '#000', '#fff', 'pose')
    agenda = (f'<rect width="1600" height="640" fill="#fff"/>'
              + P.calendario(910, 250, '#000', '#fff', 2.0)
              + f'<g transform="translate(880 40) scale(.95)">{escrevendo}</g>'
              + '<path d="M0 614H1600" stroke="#000" stroke-width="6"/>')
    (pasta / 'agenda.svg').write_text(_svg('0 0 1600 640', agenda).replace('role="img"', 'preserveAspectRatio="xMidYMid slice"'))


if __name__ == '__main__':
    SAIDA.mkdir(parents=True, exist_ok=True)
    for v in cenas.VARIANTES:
        icones(v)
        acao(v)
        corrida(v)
    porta_abrindo()
    marca()
    roleta()
    print(f'{len(list(SAIDA.glob("*.svg")))} arquivos em {SAIDA.relative_to(RAIZ)}')

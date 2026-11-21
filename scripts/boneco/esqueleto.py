"""Boneco articulado no estilo do logo (pictograma de saída de emergência).

Sistema de coordenadas do logo (800x800, chão em y=604). O boneco olha para a
ESQUERDA (para a porta). Ângulos absolutos em graus: 0 = para baixo,
+90 = para a frente (esquerda), -90 = para trás (direita), 180 = para cima.
"""
import math

L = dict(tronco=160, braco=90, antebraco=68, coxa=74, canela=90, pescoco=56)
W = dict(tronco=60, membro=38)
CABECA_R = 42

def vetor(theta, comp):
    r = math.radians(theta)
    return (-math.sin(r) * comp, math.cos(r) * comp)

def soma(p, v):
    return (p[0] + v[0], p[1] + v[1])

def f(n):
    return f'{n:.1f}'.rstrip('0').rstrip('.')

def pontos(*ps):
    return ' '.join(f'{f(x)},{f(y)}' for x, y in ps)

def montar(p):
    """p: dict com quadril (x,y) e ângulos. Retorna juntas."""
    q = p['quadril']
    j = {'quadril': q}
    j['pescoco'] = soma(q, vetor(p['tronco'], L['tronco']))
    j['cabeca'] = soma(j['pescoco'], vetor(p.get('cabeca', p['tronco'] - 12), L['pescoco']))
    # ombros: o da frente fica um pouco abaixo no tronco; o de trás, nas costas
    t = p['tronco']
    j['ombro_f'] = soma(soma(j['pescoco'], vetor(t + 180, 30)), vetor(t - 90, 22))
    j['ombro_t'] = soma(j['pescoco'], vetor(t + 90, 22))
    for lado in ('f', 't'):  # frente / trás
        cot = soma(j[f'ombro_{lado}'], vetor(p[f'braco_{lado}'], L['braco']))
        mao = soma(cot, vetor(p[f'antebraco_{lado}'], L['antebraco']))
        joe = soma(q, vetor(p[f'coxa_{lado}'], L['coxa']))
        pe = soma(joe, vetor(p[f'canela_{lado}'], L['canela']))
        j[f'cotovelo_{lado}'], j[f'mao_{lado}'] = cot, mao
        j[f'joelho_{lado}'], j[f'pe_{lado}'] = joe, pe
    return j

def svg_corpo(p, cor='currentColor', capelo=True):
    j = montar(p)
    q, n = j['quadril'], j['pescoco']
    # tronco um pouco além do quadril e do pescoço para fechar as juntas
    vx, vy = n[0] - q[0], n[1] - q[1]
    comp = math.hypot(vx, vy)
    ux, uy = vx / comp, vy / comp
    base = (q[0] - ux * 14, q[1] - uy * 14)
    topo = (n[0] + ux * 6, n[1] + uy * 6)
    partes = []
    estilo = f'fill="none" stroke="{cor}" stroke-linejoin="miter" stroke-miterlimit="3"'
    partes.append(f'<polyline points="{pontos(j["joelho_t"], q, j["pe_t"]) if False else pontos(q, j["joelho_t"], j["pe_t"])}" {estilo} stroke-width="{W["membro"]}"/>')
    partes.append(f'<polyline points="{pontos(j["ombro_t"], j["cotovelo_t"], j["mao_t"])}" {estilo} stroke-width="{W["membro"]}"/>')
    partes.append(f'<polyline points="{pontos(base, topo)}" {estilo} stroke-width="{W["tronco"]}"/>')
    partes.append(f'<polyline points="{pontos(q, j["joelho_f"], j["pe_f"])}" {estilo} stroke-width="{W["membro"]}"/>')
    partes.append(f'<polyline points="{pontos(j["ombro_f"], j["cotovelo_f"], j["mao_f"])}" {estilo} stroke-width="{W["membro"]}"/>')
    c = j['cabeca']
    partes.append(f'<circle cx="{f(c[0])}" cy="{f(c[1])}" r="{CABECA_R}" fill="{cor}"/>')
    if capelo:
        partes.append(svg_capelo(c, p.get('capelo', -10), cor))
    return '\n'.join(partes), j

def svg_capelo(c, inclinacao, cor):
    """Capelo (chapéu de formatura) com a borla caindo na frente do rosto."""
    cx, cy = c
    return (f'<g transform="translate({f(cx)} {f(cy)}) rotate({inclinacao})" fill="{cor}">'
            f'<path d="M-96 -30 L4 -64 L74 -52 L-24 -14 Z"/>'
            f'<path d="M-32 -30 L34 -46 L38 -20 C16 -30 -12 -24 -30 -12 Z"/>'
            f'<path d="M-64 -38 C-70 -26 -72 -12 -70 2" stroke="{cor}" stroke-width="4" fill="none"/>'
            f'<circle cx="-70" cy="4" r="7"/>'
            f'<path d="M-77 8 L-63 8 L-58 36 L-82 36 Z"/>'
            f'</g>')

POSE_LOGO = dict(
    quadril=(528, 452), tronco=158, cabeca=131,
    braco_f=0, antebraco_f=90,        # braço da frente segurando o chopp
    braco_t=-90, antebraco_t=-42,     # braço de trás dobrado para trás
    coxa_f=36, canela_f=0,            # perna da frente
    coxa_t=-50, canela_t=-90,         # perna de trás chutando para trás
    capelo=-12,
)

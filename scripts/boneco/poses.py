"""Poses e objetos do boneco por seção + ciclo de corrida."""
import math
from esqueleto import montar, svg_corpo, vetor, soma, f, L

CHAO = 604
OURO = '#DEAB2C'
OURO_CLARO = '#F1CF73'
VIDRO = '#BFD3DE'

def ajustar_ao_chao(p, chao=CHAO, folga=0):
    """Desloca o quadril para que o pé mais baixo toque o chão."""
    j = montar({'braco_f': 0, 'antebraco_f': 0, 'braco_t': 0, 'antebraco_t': 0, **p})
    mais_baixo = max(j['pe_f'][1], j['pe_t'][1], j['joelho_f'][1], j['joelho_t'][1])
    q = p['quadril']
    p = dict(p, quadril=(q[0], q[1] + (chao - mais_baixo) - folga))
    return p

# ---------------------------------------------------------------- objetos
def caneca(x, y, rot=0, esc=1.0, cor='currentColor'):
    """Caneca de chopp do logo: cerveja dourada, espuma branca, alça de vidro."""
    return f'''<g transform="translate({f(x)} {f(y)}) rotate({rot}) scale({esc})">
  <path d="M22 -22h12a14 14 0 0 1 14 14v16a14 14 0 0 1-14 14h-12" fill="none" stroke="{VIDRO}" stroke-width="7"/>
  <rect x="-24" y="-30" width="48" height="62" rx="5" fill="{OURO}" stroke="{VIDRO}" stroke-width="4"/>
  <path d="M-12 -18v40M0 -18v40M12 -18v40" stroke="{OURO_CLARO}" stroke-width="5" stroke-linecap="round"/>
  <path d="M-30 -28a11 11 0 0 1 8-15a13 13 0 0 1 22-5a12 12 0 0 1 22 3a10 10 0 0 1 8 13c0 6-4 8-8 8h-46c-5 0-7-2-6-4z" fill="#fff" stroke="#3a3a3a" stroke-width="2.5"/>
</g>'''

def carrinho(mao, cor, fundo):
    """Carrinho à frente (à esquerda) das mãos, rodas no chão."""
    hx, hy = mao
    # alça sai da mão e desce para a cesta
    topo = hy + 8
    x0 = hx - 34            # borda traseira (perto do boneco)
    x1 = x0 - 190           # borda da frente
    base = CHAO - 52
    return f'''<g>
  <path d="M{f(hx+4)} {f(hy)} L{f(x0+6)} {f(topo)}" stroke="{cor}" stroke-width="12" stroke-linecap="round"/>
  <path d="M{f(x0)} {f(topo)} L{f(x1)} {f(topo)} L{f(x1+22)} {f(base-28)} L{f(x0-10)} {f(base-28)} Z" fill="{OURO}" stroke="{cor}" stroke-width="10" stroke-linejoin="round"/>
  <path d="M{f(x1+14)} {f(topo+40)} H{f(x0-4)} M{f(x1+20)} {f(topo+80)} H{f(x0-8)}" stroke="{cor}" stroke-width="6" opacity=".55"/>
  <path d="M{f(x0-10)} {f(base-28)} L{f(x0-4)} {f(base)} H{f(x1+30)}" fill="none" stroke="{cor}" stroke-width="10" stroke-linejoin="round"/>
  <circle cx="{f(x0-24)}" cy="{f(CHAO-22)}" r="20" fill="{cor}"/><circle cx="{f(x0-24)}" cy="{f(CHAO-22)}" r="7" fill="{fundo}"/>
  <circle cx="{f(x1+44)}" cy="{f(CHAO-22)}" r="20" fill="{cor}"/><circle cx="{f(x1+44)}" cy="{f(CHAO-22)}" r="7" fill="{fundo}"/>
</g>'''

def saco_dinheiro(mao, cor, fundo):
    hx, hy = mao
    return f'''<g transform="translate({f(hx)} {f(hy)})">
  <path d="M-14 6 L-22 -8 H22 L14 6 C46 18 60 46 58 74 C56 104 30 118 0 118 C-30 118 -56 104 -58 74 C-60 46 -46 18 -14 6Z" fill="{OURO}" stroke="{cor}" stroke-width="6" stroke-linejoin="round"/>
  <path d="M-24 4 H24" stroke="{cor}" stroke-width="10" stroke-linecap="round"/>
  <path d="M14 56c-4-8-12-10-18-10c-10 0-16 5-16 12c0 16 34 8 34 24c0 8-8 13-18 13c-8 0-15-3-19-10M-2 38v76" fill="none" stroke="{cor}" stroke-width="8" stroke-linecap="round"/>
</g>'''

def moeda(x, y, cor):
    return f'<g transform="translate({f(x)} {f(y)})"><ellipse rx="22" ry="22" fill="{OURO}" stroke="{cor}" stroke-width="5"/><path d="M0 -10v20" stroke="{cor}" stroke-width="5" stroke-linecap="round"/></g>'

def caixa(j, cor):
    """Caixa segurada com as duas mãos na frente do peito."""
    mf, mt = j['mao_f'], j['mao_t']
    cx = (mf[0] + mt[0]) / 2 - 18
    cy = (mf[1] + mt[1]) / 2 - 6
    return f'''<g transform="translate({f(cx)} {f(cy)})">
  <rect x="-78" y="-62" width="150" height="122" fill="{OURO}" stroke="{cor}" stroke-width="8"/>
  <path d="M-78 -26 H72 M-6 -62 V-26" stroke="{cor}" stroke-width="8"/>
  <rect x="24" y="12" width="34" height="26" fill="{cor}"/>
</g>'''

def chave_inglesa(mao, ang, cor):
    hx, hy = mao
    return f'''<g transform="translate({f(hx)} {f(hy)}) rotate({ang})">
  <rect x="-9" y="-14" width="18" height="118" rx="6" fill="{OURO}" stroke="{cor}" stroke-width="5"/>
  <path d="M-30 104 a30 30 0 0 0 60 0 l-8 -12 v26 h-44 v-26z" fill="{OURO}" stroke="{cor}" stroke-width="5" stroke-linejoin="round" transform="rotate(180 0 116)"/>
</g>'''

def capacete(cabeca, ang, cor):
    cx, cy = cabeca
    return f'''<g transform="translate({f(cx)} {f(cy)}) rotate({ang})">
  <path d="M-46 -4 C-46 -40 -24 -60 0 -60 C24 -60 46 -40 46 -4 Z" fill="{OURO}" stroke="{cor}" stroke-width="6"/>
  <path d="M-62 -4 H58" stroke="{OURO}" stroke-width="14" stroke-linecap="round"/>
  <path d="M-8 -60 V-14" stroke="{cor}" stroke-width="7" opacity=".6"/>
</g>'''

def prancheta(mao, ang, cor, fundo):
    hx, hy = mao
    return f'''<g transform="translate({f(hx)} {f(hy)}) rotate({ang})">
  <rect x="-58" y="-70" width="78" height="104" rx="6" fill="{fundo}" stroke="{cor}" stroke-width="7"/>
  <rect x="-34" y="-80" width="30" height="18" rx="4" fill="{OURO}" stroke="{cor}" stroke-width="4"/>
  <path d="M-44 -44 H6 M-44 -24 H6 M-44 -4 H-8" stroke="{cor}" stroke-width="7" stroke-linecap="round"/>
</g>'''

def caneta(mao, ang, cor):
    hx, hy = mao
    return f'<g transform="translate({f(hx)} {f(hy)}) rotate({ang})"><path d="M-4 -6 L-4 -58 L4 -58 L4 -6 L0 4 Z" fill="{OURO}" stroke="{cor}" stroke-width="4" stroke-linejoin="round"/></g>'

def cadeira(j, cor):
    qx, qy = j['quadril']
    return f'''<g fill="none" stroke="{cor}" stroke-width="16" stroke-linejoin="miter">
  <path d="M{f(qx+46)} {f(qy-130)} V{f(qy+22)} H{f(qx-70)}"/>
  <path d="M{f(qx+40)} {f(qy+22)} V{CHAO} M{f(qx-62)} {f(qy+22)} V{CHAO}"/>
</g>'''

def mesa_baixa(x, cor):
    return f'<g fill="none" stroke="{cor}" stroke-width="16"><path d="M{f(x-110)} {CHAO-150} H{f(x+20)} M{f(x-96)} {CHAO-150} V{CHAO} M{f(x+6)} {CHAO-150} V{CHAO}"/></g>'

def calendario(x, y, cor, fundo, esc=1.0):
    dias = ''
    for lin in range(3):
        for col in range(4):
            dx = -66 + col * 36; dy = -10 + lin * 32
            preench = OURO if (lin, col) == (1, 2) else cor
            dias += f'<rect x="{dx}" y="{dy}" width="22" height="20" fill="{preench}"/>'
    return f'''<g transform="translate({f(x)} {f(y)}) scale({esc})">
  <rect x="-88" y="-62" width="166" height="160" rx="8" fill="{fundo}" stroke="{cor}" stroke-width="9"/>
  <rect x="-88" y="-62" width="166" height="40" rx="8" fill="{OURO}" stroke="{cor}" stroke-width="9"/>
  <path d="M-50 -80 V-46 M40 -80 V-46" stroke="{cor}" stroke-width="12" stroke-linecap="round"/>
  {dias}
</g>'''

def casa(x, cor, fundo):
    return f'''<g>
  <path d="M{f(x-150)} {CHAO} V{CHAO-170} L{f(x-55)} {CHAO-262} L{f(x+40)} {CHAO-170} V{CHAO} Z" fill="{fundo}" stroke="{cor}" stroke-width="12" stroke-linejoin="miter"/>
  <rect x="{f(x-82)}" y="{CHAO-110}" width="54" height="110" fill="{OURO}" stroke="{cor}" stroke-width="10"/>
  <rect x="{f(x-130)}" y="{CHAO-150}" width="34" height="34" fill="{OURO}" stroke="{cor}" stroke-width="7"/>
</g>'''

def celular(mao, ang, cor):
    hx, hy = mao
    return f'''<g transform="translate({f(hx)} {f(hy)}) rotate({ang})">
  <rect x="-22" y="-48" width="44" height="80" rx="8" fill="{cor}"/>
  <rect x="-15" y="-38" width="30" height="56" rx="3" fill="{OURO}"/>
</g>'''

def flash(x, y):
    return f'<g transform="translate({f(x)} {f(y)})" stroke="{OURO}" stroke-width="7" stroke-linecap="round"><path d="M0 -26V-44M-22 -14L-36 -24M22 -14L36 -24"/></g>'

def chave(mao, ang, cor):
    hx, hy = mao
    return f'''<g transform="translate({f(hx)} {f(hy)}) rotate({ang})">
  <circle cx="0" cy="0" r="26" fill="none" stroke="{OURO}" stroke-width="13"/>
  <path d="M-26 0 H-120 M-92 0 V22 M-110 0 V18" stroke="{OURO}" stroke-width="13" stroke-linecap="butt"/>
  <circle cx="0" cy="0" r="26" fill="none" stroke="{cor}" stroke-width="3" opacity=".35"/>
</g>'''

def fechadura(x, y, cor, fundo):
    return f'''<g transform="translate({f(x)} {f(y)})">
  <path d="M-36 -30 V-56 a36 36 0 0 1 72 0 V-30" fill="none" stroke="{cor}" stroke-width="14"/>
  <rect x="-58" y="-34" width="116" height="100" rx="10" fill="{OURO}" stroke="{cor}" stroke-width="9"/>
  <circle cx="0" cy="8" r="12" fill="{cor}"/><rect x="-5" y="10" width="10" height="28" fill="{cor}"/>
</g>'''

def engrenagem(x, y, raio, rot, cor):
    dentes = 10
    pts = []
    for i in range(dentes * 4):
        a = math.radians(i * 360 / (dentes * 4) + rot)
        r = raio if (i % 4) in (0, 1) else raio * 0.8
        pts.append(f'{f(x + r * math.cos(a))},{f(y + r * math.sin(a))}')
    return f'''<g>
  <polygon points="{' '.join(pts)}" fill="{OURO}" stroke="{cor}" stroke-width="8" stroke-linejoin="round"/>
  <circle cx="{f(x)}" cy="{f(y)}" r="{f(raio*0.32)}" fill="{cor}"/>
</g>'''

def mochila(j, tronco, cor):
    n, q = j['pescoco'], j['quadril']
    mx = (n[0] + q[0]) / 2; my = (n[1] + q[1]) / 2
    return f'''<g transform="translate({f(mx)} {f(my)}) rotate({f(180 - tronco)})">
  <rect x="22" y="-64" width="58" height="104" rx="16" fill="{OURO}" stroke="{cor}" stroke-width="7"/>
  <rect x="30" y="-6" width="42" height="30" rx="6" fill="none" stroke="{cor}" stroke-width="6"/>
</g>'''

def maos_acenando(mao, cor):
    hx, hy = mao
    return f'<g stroke="{OURO}" stroke-width="7" stroke-linecap="round" fill="none"><path d="M{f(hx-40)} {f(hy-30)} q-10 18 0 36 M{f(hx+40)} {f(hy-30)} q10 18 0 36"/></g>'

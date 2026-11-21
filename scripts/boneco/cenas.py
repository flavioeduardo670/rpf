"""Cenas do boneco por seção: pose parada, ação (cabeçalho) e corrida (transição)."""
import math
from esqueleto import montar, svg_corpo, vetor, soma, f, L, CABECA_R, POSE_LOGO
import poses as P

def angulo_para(dx, dy):
    return math.degrees(math.atan2(-dx, dy))

def ik(ombro, alvo, l1, l2, dobra=1):
    """Ângulos (braço, antebraço) para a mão alcançar o alvo. dobra=+1/-1 escolhe o lado do cotovelo."""
    dx, dy = alvo[0] - ombro[0], alvo[1] - ombro[1]
    d = max(1e-6, min(math.hypot(dx, dy), l1 + l2 - 0.5))
    base = angulo_para(dx, dy)
    cosa = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    a = math.degrees(math.acos(max(-1, min(1, cosa))))
    sup = base + dobra * a
    cot = soma(ombro, vetor(sup, l1))
    ante = angulo_para(alvo[0] - cot[0], alvo[1] - cot[1])
    return sup, ante

def com_alvos(p):
    """Resolve 'alvo_f'/'alvo_t' (x, y, dobra) em ângulos de braço."""
    p = dict(p)
    for lado in ('f', 't'):
        p.setdefault(f'braco_{lado}', 0); p.setdefault(f'antebraco_{lado}', 0)
    j = montar(p)
    for lado in ('f', 't'):
        alvo = p.get(f'alvo_{lado}')
        if alvo:
            dobra = alvo[2] if len(alvo) > 2 else 1
            p[f'braco_{lado}'], p[f'antebraco_{lado}'] = ik(j[f'ombro_{lado}'], alvo[:2], L['braco'], L['antebraco'], dobra)
    return p

def boca(j, p):
    c = j['cabeca']
    inclin = p.get('cabeca', p['tronco'] - 12) - 180   # >0 = cabeça para trás
    return soma(c, vetor(74 + inclin, CABECA_R * 0.92))

# ------------------------------------------------------------ ciclo de corrida
PERNA = [(36, 18), (18, -4), (0, -14), (-24, -46), (-40, -88), (-18, -122), (22, -72), (44, 8)]
BRACO = [(-42, 30), (-26, 52), (0, 84), (30, 112), (52, 138), (32, 118), (2, 80), (-26, 40)]
VOO = [0, 0, 0, 4, 12, 14, 8, 2]

def corrida(k, chao=P.CHAO, x=520):
    """Quadro k (0..7) da corrida, virado para a esquerda."""
    pf, pt = PERNA[k], PERNA[(k + 4) % 8]
    bf, bt = BRACO[(k + 4) % 8], BRACO[k]     # braço oposto à perna do mesmo lado
    p = dict(quadril=(x, 400), tronco=158, cabeca=142,
             coxa_f=pf[0], canela_f=pf[1], coxa_t=pt[0], canela_t=pt[1],
             braco_f=bf[0], antebraco_f=bf[1], braco_t=bt[0], antebraco_t=bt[1], capelo=-12)
    p = P.ajustar_ao_chao(p, chao)
    q = p['quadril']
    return dict(p, quadril=(q[0], q[1] - VOO[k]))

# ------------------------------------------------------------ cenas
def _figura(p, cor, capelo=True):
    corpo, j = svg_corpo(p, cor=cor, capelo=capelo)
    return corpo, j

def cena(variante, cor='#000', fundo='#fff', modo='pose', k=0, x=520):
    """Retorna (svg, juntas). modo: 'pose' (parado), 'acao' (quadro k da ação), 'corrida' (quadro k)."""
    fn = globals().get(f'cena_{variante}', cena_inicio)
    return fn(cor, fundo, modo, k, x)

def _corrida_com(p_extra, k, x):
    p = corrida(k, x=x)
    p.update(p_extra)
    return com_alvos(p)

# --- início: o logo (correndo para a porta com o chopp)
def cena_inicio(cor, fundo, modo, k, x):
    if modo == 'pose':
        p = dict(POSE_LOGO)
    else:
        p = _corrida_com(dict(braco_f=0, antebraco_f=90), k, x)
    corpo, j = _figura(p, cor)
    m = j['mao_f']
    return corpo + P.caneca(m[0] - 36, m[1] - 8, 0, 1.2), j

# --- compras: empurrando o carrinho, que vai na frente
def cena_compras(cor, fundo, modo, k, x):
    if modo == 'pose':
        base = dict(quadril=(600, 440), tronco=150, cabeca=140, coxa_f=40, canela_f=6, coxa_t=-40, canela_t=-84, capelo=-14)
        base = P.ajustar_ao_chao(base)
    else:
        base = corrida(k, x=x + 40)
        base.update(tronco=150, cabeca=140)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    alca = (j0['quadril'][0] - 128, j0['quadril'][1] - 44)
    p = com_alvos(dict(base, alvo_f=(alca[0], alca[1], -1), alvo_t=(alca[0] + 10, alca[1] - 4, -1)))
    corpo, j = _figura(p, cor)
    return corpo + P.carrinho(j['mao_f'], cor, fundo), j

# --- rock: virando o chopp
def cena_rock(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=84, antebraco_f=128), k, x)
        corpo, j = _figura(p, cor)
        m = j['mao_f']
        return corpo + P.caneca(m[0] - 30, m[1] - 22, -18, 1.1), j
    gole = [0, 6, 10, 6][k % 4] if modo == 'acao' else 8
    base = dict(quadril=(470, 440), tronco=190 + gole * 0.4, cabeca=206 + gole, coxa_f=14, canela_f=2, coxa_t=-14, canela_t=-4, capelo=-8 - gole * 0.6)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    b = boca(j0, base)
    inclin = 70 + gole * 3                         # quanto a caneca está virada
    centro = soma(b, vetor(90 + 24, 46))
    alca = soma(centro, (44 * math.cos(math.radians(inclin)), 44 * math.sin(math.radians(inclin))))
    qx, qy = j0['quadril']
    p = com_alvos(dict(base, alvo_f=(alca[0], alca[1], -1), alvo_t=(qx + 24, qy - 12, -1)))
    corpo, j = _figura(p, cor)
    return corpo + P.caneca(centro[0], centro[1], inclin, 1.15), j

# --- financeiro: andando com o saco de dinheiro, jogando uma moeda para cima
def cena_financeiro(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=24, antebraco_f=70), k, x)
        corpo, j = _figura(p, cor)
        return corpo + P.saco_dinheiro(j['mao_f'], cor, fundo), j
    fase = [0, 1, 2, 1][k % 4] if modo == 'acao' else 1
    base = dict(quadril=(520, 440), tronco=168, cabeca=164, braco_t=-14, antebraco_t=-8,
                coxa_f=22, canela_f=2, coxa_t=-20, canela_t=-24, capelo=-8)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0))
    o = j0['ombro_f']
    p = com_alvos(dict(base, alvo_f=(o[0] - 92, o[1] + 22 - fase * 10, -1)))
    corpo, j = _figura(p, cor)
    mf = j['mao_f']
    altura = [24, 70, 110][fase]
    return corpo + P.saco_dinheiro(j['mao_t'], cor, fundo) + P.moeda(mf[0] - 4, mf[1] - altura, cor), j

# --- almoxarifado: carregando a caixa com as duas mãos
def cena_almoxarifado(cor, fundo, modo, k, x):
    if modo == 'corrida':
        base = corrida(k, x=x); base.update(tronco=170)
    else:
        passo = [0, 1, 2, 1][k % 4] if modo == 'acao' else 1
        base = dict(quadril=(520, 440), tronco=172 + passo, cabeca=166, coxa_f=12 + passo * 8, canela_f=0, coxa_t=-12 - passo * 8, canela_t=-30, capelo=-8)
        base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    n = j0['pescoco']
    p = com_alvos(dict(base, alvo_f=(n[0] - 86, n[1] + 58, 1), alvo_t=(n[0] - 70, n[1] + 30, 1)))
    corpo, j = _figura(p, cor)
    return corpo + P.caixa(j, cor), j

# --- manutenção: ajoelhado, apertando o cano com a chave inglesa (capacete no lugar do capelo)
def cena_manutencao(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=44, antebraco_f=118), k, x)
        corpo, j = _figura(p, cor, capelo=False)
        return corpo + P.capacete(j['cabeca'], -12, cor) + P.chave_inglesa(j['mao_f'], 210, cor), j
    golpe = [0, 1, 2, 1][k % 4] if modo == 'acao' else 2
    base = dict(quadril=(560, 470), tronco=160, cabeca=146,
                coxa_f=88, canela_f=0, coxa_t=-4, canela_t=-90, capelo=0)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    o = j0['ombro_f']
    porca = (o[0] - 150, P.CHAO - 84)
    alvo = [(o[0] - 70, o[1] - 40), (o[0] - 96, o[1] + 10), (o[0] - 92, o[1] + 62)][golpe]
    ang = [150, 205, 250][golpe]
    p = com_alvos(dict(base, alvo_f=(alvo[0], alvo[1], -1), alvo_t=(o[0] - 74, o[1] + 82, 1)))
    corpo, j = _figura(p, cor, capelo=False)
    cano = (f'<path d="M{f(porca[0]-70)} {P.CHAO} V{f(porca[1])} H{f(porca[0]+10)}" fill="none" stroke="{cor}" stroke-width="24"/>'
            f'<rect x="{f(porca[0]-6)}" y="{f(porca[1]-20)}" width="26" height="40" fill="{P.OURO}" stroke="{cor}" stroke-width="5"/>')
    faisca = (f'<g stroke="{P.OURO}" stroke-width="7" stroke-linecap="round"><path d="M{f(porca[0]+4)} {f(porca[1]-34)}l-10 -22'
              f'M{f(porca[0]+28)} {f(porca[1]-30)}l10 -20M{f(porca[0]-18)} {f(porca[1]-24)}l-22 -10"/></g>') if golpe == 2 else ''
    return cano + corpo + P.capacete(j['cabeca'], base['cabeca'] - 180 + 24, cor) + P.chave_inglesa(j['mao_f'], ang, cor) + faisca, j

# --- reuniões: sentado escrevendo a ata
def cena_reunioes(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=40, antebraco_f=120), k, x)
        corpo, j = _figura(p, cor)
        return corpo + P.prancheta(j['mao_f'], -20, cor, fundo), j
    escreve = [0, 1, 2, 1][k % 4] if modo == 'acao' else 1
    base = dict(quadril=(540, 456), tronco=176, cabeca=166, coxa_f=90, canela_f=2, coxa_t=86, canela_t=-2, capelo=-6)
    base['quadril'] = (540, P.CHAO - L['canela'] - 4)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    n = j0['pescoco']
    prancha = (n[0] - 92, n[1] + 70)
    p = com_alvos(dict(base, alvo_f=(prancha[0] + 6, prancha[1] + 20, 1),
                       alvo_t=(prancha[0] - 10 + escreve * 10, prancha[1] - 30 + escreve * 6, 1)))
    corpo, j = _figura(p, cor)
    return (P.cadeira(j, cor) + corpo + P.prancheta((prancha[0] + 14, prancha[1] + 18), -24, cor, fundo)
            + P.caneta(j['mao_t'], 20, cor)), j

# --- calendário: apontando para o calendário grande
def cena_calendario(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=30, antebraco_f=100), k, x)
        corpo, j = _figura(p, cor)
        m = j['mao_f']
        return corpo + P.calendario(m[0] - 40, m[1] - 20, cor, fundo, 0.55), j
    toque = [0, 1, 0, 1][k % 4] if modo == 'acao' else 0
    base = dict(quadril=(560, 440), tronco=184, cabeca=196, coxa_f=12, canela_f=0, coxa_t=-12, canela_t=-2, capelo=-8)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    qx, qy = j0['quadril']
    cal = (qx - 240, qy - 150)
    p = com_alvos(dict(base, alvo_f=(cal[0] + 84 - toque * 14, cal[1] + 20, -1), alvo_t=(qx + 22, qy - 14, -1)))
    corpo, j = _figura(p, cor)
    return P.calendario(cal[0], cal[1], cor, fundo) + corpo, j

# --- moradores: chegando em casa de mochila e acenando
def cena_moradores(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com({}, k, x)
        corpo, j = _figura(p, cor)
        return P.mochila(j, p['tronco'], cor) + corpo, j
    aceno = [0, 1, 2, 1][k % 4] if modo == 'acao' else 1
    base = dict(quadril=(600, 440), tronco=176, cabeca=170, braco_t=-20, antebraco_t=10,
                coxa_f=16, canela_f=0, coxa_t=-16, canela_t=-24, capelo=-8)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0))
    o = j0['ombro_f']
    mao = (o[0] - 128 + aceno * 18, o[1] - 86 - aceno * 6)
    p = com_alvos(dict(base, alvo_f=(mao[0], mao[1], -1)))
    corpo, j = _figura(p, cor)
    return P.casa(j['quadril'][0] - 270, cor, fundo) + P.mochila(j, p['tronco'], cor) + corpo, j

# --- perfil: tirando uma selfie
def cena_perfil(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=70, antebraco_f=140), k, x)
        corpo, j = _figura(p, cor)
        return corpo + P.celular(j['mao_f'], 20, cor), j
    clique = (k % 4 == 2) if modo == 'acao' else True
    base = dict(quadril=(540, 440), tronco=186, cabeca=200, coxa_f=10, canela_f=0, coxa_t=-12, canela_t=-2, capelo=-4)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    c = j0['cabeca']
    tel = (c[0] - 130, c[1] - 40)
    p = com_alvos(dict(base, alvo_f=(tel[0] + 8, tel[1] + 16, -1), alvo_t=(c[0] + 60, c[1] - 50, -1)))
    corpo, j = _figura(p, cor)
    paz = f'<g stroke="{cor}" stroke-width="14" stroke-linecap="butt"><path d="M{f(j["mao_t"][0])} {f(j["mao_t"][1])} l-6 -36 M{f(j["mao_t"][0])} {f(j["mao_t"][1])} l16 -32"/></g>'
    return corpo + paz + P.celular(tel, 20, cor) + (P.flash(tel[0], tel[1] - 40) if clique else ''), j

# --- acessos: encaixando a chave na fechadura, que abre
def cena_acessos(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=46, antebraco_f=92), k, x)
        corpo, j = _figura(p, cor)
        m = j['mao_f']
        return corpo + P.chave((m[0] + 10, m[1]), 0, cor), j
    passo = [0, 1, 2, 2][k % 4] if modo == 'acao' else 2
    aberta = (modo != 'acao') or k % 4 == 3
    base = dict(quadril=(600, 440), tronco=162, cabeca=150, coxa_f=30, canela_f=0, coxa_t=-30, canela_t=-40, capelo=-12)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    o = j0['ombro_f']
    fech = (o[0] - 270, o[1] + 30)
    mao = (fech[0] + 140 + (2 - passo) * 26, fech[1] + 8)
    p = com_alvos(dict(base, alvo_f=(mao[0] + 8, mao[1], -1), alvo_t=(mao[0] + 22, mao[1] + 10, -1)))
    corpo, j = _figura(p, cor)
    trava = P.fechadura(fech[0], fech[1], cor, fundo)
    if aberta:
        trava = trava.replace('<path d="M-36 -30 V-56', '<path transform="translate(0 -22)" d="M-36 -30 V-56')
    return trava + P.chave(mao, 0, cor) + corpo, j

# --- configurações: empurrando uma engrenagem grande
def cena_configuracoes(cor, fundo, modo, k, x):
    if modo == 'corrida':
        p = _corrida_com(dict(braco_f=40, antebraco_f=100), k, x)
        corpo, j = _figura(p, cor)
        m = j['mao_f']
        return corpo + P.engrenagem(m[0] - 46, m[1], 50, k * 9, cor), j
    rot = [0, 9, 18, 27][k % 4] if modo == 'acao' else 0
    base = dict(quadril=(600, 440), tronco=132, cabeca=124, coxa_f=50, canela_f=10, coxa_t=-46, canela_t=-50, capelo=-18)
    base = P.ajustar_ao_chao(base)
    j0 = montar(dict(base, braco_f=0, antebraco_f=0, braco_t=0, antebraco_t=0))
    o = j0['ombro_f']
    raio = 120
    eng = (o[0] - 90 - raio, P.CHAO - raio - 6)
    p = com_alvos(dict(base, alvo_f=(eng[0] + raio * 0.86, eng[1] - 14, 1), alvo_t=(eng[0] + raio * 0.84, eng[1] + 28, 1)))
    corpo, j = _figura(p, cor)
    return P.engrenagem(eng[0], eng[1], raio, rot, cor) + corpo, j

VARIANTES = ['inicio', 'moradores', 'financeiro', 'compras', 'almoxarifado', 'manutencao',
             'rock', 'reunioes', 'calendario', 'perfil', 'acessos', 'configuracoes']

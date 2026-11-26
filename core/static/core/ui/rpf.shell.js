/* Menu no celular + troca de página com o boneco entrando pela porta. */
(function () {
    'use strict';

    var html = document.documentElement;

    // ---------- Menu do topo no celular ----------
    var topo = document.querySelector('.rpf-topo');
    var toggle = document.querySelector('.rpf-menu-toggle');
    if (topo && toggle) {
        toggle.addEventListener('click', function () {
            var aberto = topo.classList.toggle('aberto');
            toggle.setAttribute('aria-expanded', aberto ? 'true' : 'false');
        });
    }

    // ---------- Boneco do cabeçalho: repete a ação ao passar o mouse ----------
    var bonecoCabecalho = document.querySelector('.rpf-cabecalho__boneco');
    if (bonecoCabecalho) {
        var reiniciar = function () {
            // Uma imagem nova reinicia a animação interna do SVG.
            var novo = bonecoCabecalho.cloneNode(true);
            bonecoCabecalho.parentNode.replaceChild(novo, bonecoCabecalho);
            bonecoCabecalho = novo;
            bonecoCabecalho.addEventListener('mouseenter', reiniciar, { once: true });
            bonecoCabecalho.addEventListener('click', reiniciar, { once: true });
        };
        bonecoCabecalho.addEventListener('mouseenter', reiniciar, { once: true });
        bonecoCabecalho.addEventListener('click', reiniciar, { once: true });
    }

    // ---------- Transição entre páginas ----------
    var overlay = document.querySelector('.rpf-transicao');
    var mapaEl = document.getElementById('rpf-mapa-secoes');
    var reduzMovimento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    if (!overlay || !mapaEl) return;

    var mapa = { secoes: [], inicio: null, chegada: null };
    try { mapa = JSON.parse(mapaEl.textContent); } catch (e) { /* sem mapa, sem animação */ }
    var DURACAO = 880; // mesma duração da cena em corrida-*.svg

    function secaoDe(caminho) {
        for (var i = 0; i < mapa.secoes.length; i++) {
            var s = mapa.secoes[i];
            if (caminho === s.prefixo || caminho.indexOf(s.prefixo + '/') === 0) return s;
        }
        return mapa.inicio;
    }

    function trocarCena(src) {
        // Sempre uma <img> nova, para a animação do SVG começar do zero.
        var antiga = overlay.querySelector('.rpf-transicao__cena');
        var nova = antiga.cloneNode(false);
        nova.src = src;
        antiga.parentNode.replaceChild(nova, antiga);
    }

    // Chegada: a página carregou atrás da porta; ela abre e a página aparece.
    if (html.classList.contains('rpf-chegando')) {
        if (mapa.chegada) trocarCena(mapa.chegada);
        var terminarChegada = function () {
            requestAnimationFrame(function () {
                html.classList.add('rpf-chegou');
                setTimeout(function () { html.classList.remove('rpf-chegando', 'rpf-chegou'); }, 700);
            });
        };
        if (document.readyState === 'loading') {
            document.addEventListener('DOMContentLoaded', terminarChegada);
        } else {
            terminarChegada();
        }
    }

    // Pré-carrega as cenas quando o navegador estiver ocioso (são pequenas).
    var preCarregar = function () {
        var conexao = navigator.connection;
        if (conexao && conexao.saveData) return;
        mapa.secoes.concat(mapa.inicio ? [mapa.inicio] : []).forEach(function (s) {
            var img = new Image();
            img.src = s.corrida;
        });
    };
    if (!reduzMovimento) {
        if ('requestIdleCallback' in window) {
            window.requestIdleCallback(preCarregar, { timeout: 4000 });
        } else {
            setTimeout(preCarregar, 2500);
        }
    }

    // Links que não devem animar: downloads, exportações, PDFs, admin, outras abas.
    var SEM_ANIMACAO = /(\.(pdf|csv|xlsx?)$)|(\/(pdf|boleto|exportar)\/?$)|(\/exportar\/)|(^\/admin\/)|(^\/media\/)|(^\/static\/)/;

    document.addEventListener('click', function (e) {
        if (reduzMovimento || e.defaultPrevented || e.button !== 0) return;
        if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
        var link = e.target.closest ? e.target.closest('a[href]') : null;
        if (!link) return;
        if ((link.target && link.target !== '_self') || link.hasAttribute('download')) return;
        if (link.hasAttribute('data-sem-transicao')) return;

        var url;
        try { url = new URL(link.href, window.location.href); } catch (err) { return; }
        if (url.origin !== window.location.origin) return;
        if (url.pathname === window.location.pathname && url.search === window.location.search) return;
        if (SEM_ANIMACAO.test(url.pathname)) return;

        var secao = secaoDe(url.pathname);
        if (!secao) return;
        e.preventDefault();

        trocarCena(secao.corrida);
        var destino = overlay.querySelector('.rpf-transicao__destino span');
        if (destino) destino.textContent = secao.rotulo;

        html.classList.remove('rpf-chegando', 'rpf-chegou');
        html.classList.add('rpf-saindo');
        try { sessionStorage.setItem('rpf-transicao', '1'); } catch (err) { /* modo privado */ }
        setTimeout(function () { window.location.href = url.href; }, DURACAO);
    });

    // Voltar pelo navegador (bfcache) não deve deixar a porta na tela.
    window.addEventListener('pageshow', function (e) {
        if (e.persisted) html.classList.remove('rpf-saindo', 'rpf-chegando', 'rpf-chegou');
    });
})();

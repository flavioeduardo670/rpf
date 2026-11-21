/* Roleta de imagens do título da página inicial. */
(function () {
    'use strict';

    var reduzMovimento = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    var INTERVALO = 6000;

    document.querySelectorAll('[data-roleta]').forEach(function (roleta) {
        var trilho = roleta.querySelector('.rpf-roleta__trilho');
        var slides = Array.prototype.slice.call(roleta.querySelectorAll('.rpf-roleta__slide'));
        var legenda = roleta.querySelector('.rpf-roleta__legenda span');
        var pontos = Array.prototype.slice.call(roleta.querySelectorAll('.rpf-roleta__ponto'));
        var botaoPausa = roleta.querySelector('[data-roleta-pausa]');
        var atual = 0;
        var timer = null;
        var pausadoPeloUsuario = reduzMovimento;

        if (slides.length < 2) {
            var controles = roleta.querySelector('.rpf-roleta__controles');
            if (controles) controles.hidden = true;
            return;
        }

        function mostrar(indice) {
            atual = (indice + slides.length) % slides.length;
            trilho.style.transform = 'translateX(' + (-100 * atual) + '%)';
            slides.forEach(function (slide, i) {
                slide.setAttribute('aria-hidden', i === atual ? 'false' : 'true');
            });
            pontos.forEach(function (ponto, i) {
                ponto.setAttribute('aria-current', i === atual ? 'true' : 'false');
            });
            if (legenda) legenda.textContent = slides[atual].getAttribute('data-legenda') || '';
        }

        function parar() { clearInterval(timer); timer = null; }
        function iniciar() {
            parar();
            if (!pausadoPeloUsuario) timer = setInterval(function () { mostrar(atual + 1); }, INTERVALO);
        }

        roleta.querySelector('[data-roleta-anterior]').addEventListener('click', function () { mostrar(atual - 1); iniciar(); });
        roleta.querySelector('[data-roleta-proximo]').addEventListener('click', function () { mostrar(atual + 1); iniciar(); });
        pontos.forEach(function (ponto, i) {
            ponto.addEventListener('click', function () { mostrar(i); iniciar(); });
        });

        if (botaoPausa) {
            var atualizarPausa = function () {
                botaoPausa.setAttribute('aria-label', pausadoPeloUsuario ? 'Retomar a roleta' : 'Pausar a roleta');
                botaoPausa.querySelector('[data-icone="pausa"]').hidden = pausadoPeloUsuario;
                botaoPausa.querySelector('[data-icone="play"]').hidden = !pausadoPeloUsuario;
            };
            botaoPausa.addEventListener('click', function () {
                pausadoPeloUsuario = !pausadoPeloUsuario;
                atualizarPausa();
                iniciar();
            });
            atualizarPausa();
        }

        // Pausa enquanto o mouse ou o foco do teclado estiverem na roleta.
        roleta.addEventListener('mouseenter', parar);
        roleta.addEventListener('mouseleave', iniciar);
        roleta.addEventListener('focusin', parar);
        roleta.addEventListener('focusout', iniciar);

        // Setas do teclado quando a roleta está em foco.
        roleta.addEventListener('keydown', function (e) {
            if (e.key === 'ArrowLeft') { mostrar(atual - 1); }
            if (e.key === 'ArrowRight') { mostrar(atual + 1); }
        });

        mostrar(0);
        iniciar();
    });
})();

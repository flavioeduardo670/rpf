"""Novo visual: saudação da página inicial, boneco por seção e menu por permissão."""
from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.context_processors import LOOPS, secao_por_caminho


class SaudacaoInicioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'x', first_name='Demo')
        self.client.force_login(self.user)

    def test_saudacao_com_nome_e_boneco_do_inicio(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'rpf-saudacao')
        self.assertContains(response, 'Demo.')
        self.assertContains(response, 'core/boneco/loop-inicio.webp')
        self.assertContains(response, 'Nenhum rock marcado ainda')
        self.assertNotContains(response, 'data-roleta')

    def test_atalhos_em_blocos_com_destaques(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'rpf-atalho--destaque')  # financeiro
        self.assertContains(response, 'rpf-atalho--escuro')    # rocks
        self.assertContains(response, 'href="%s"' % reverse('financeiro'))
        self.assertContains(response, 'Abrir financeiro')

    def test_menu_no_topo_e_rodape_com_conta(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'class="rpf-topo"')
        self.assertContains(response, 'class="rpf-rodape"')
        self.assertNotContains(response, 'rpf-lateral')


class BonecoPorSecaoTests(TestCase):
    def test_variante_por_caminho(self):
        self.assertEqual(secao_por_caminho('/compras/')['variante'], 'compras')
        self.assertEqual(secao_por_caminho('/rock/1/lotes/')['variante'], 'rock')
        self.assertEqual(secao_por_caminho('/os/lista/')['variante'], 'manutencao')
        self.assertEqual(secao_por_caminho('/')['variante'], 'inicio')
        self.assertEqual(secao_por_caminho('/compraszzz/')['variante'], 'inicio')

    def test_cabecalho_mostra_boneco_da_pagina(self):
        user = User.objects.create_superuser('admin', 'a@a.com', 'x')
        self.client.force_login(user)
        response = self.client.get(reverse('compras'))
        self.assertContains(response, 'core/boneco/loop-compras.webp')
        self.assertContains(response, 'rpf-transicao')  # cena da troca de página
        self.assertContains(response, 'corrida-compras.svg')  # mapa usado pela animação

    def test_secao_sem_loop_usa_a_acao_em_svg(self):
        user = User.objects.create_superuser('admin', 'a@a.com', 'x')
        self.client.force_login(user)
        response = self.client.get(reverse('gerenciar_acessos'))
        self.assertContains(response, 'core/boneco/acao-acessos-preto.svg')

    def test_todos_os_desenhos_existem(self):
        from pathlib import Path
        from django.conf import settings
        from core.context_processors import SECOES
        pasta = Path(settings.BASE_DIR) / 'core' / 'static' / 'core' / 'boneco'
        for variante in ['inicio'] + [s[1] for s in SECOES]:
            for nome in (f'acao-{variante}-preto.svg', f'icone-{variante}-branco.svg',
                         f'icone-{variante}-preto.svg', f'corrida-{variante}.svg'):
                self.assertTrue((pasta / nome).exists(), nome)
        for variante in LOOPS:
            self.assertTrue((pasta / f'loop-{variante}.webp').exists(), variante)


class MenuPorPermissaoTests(TestCase):
    def test_menu_mostra_so_modulos_permitidos(self):
        user = User.objects.create_user('fin', password='x')
        user.groups.add(Group.objects.create(name='Financeiro'))
        self.client.force_login(user)
        response = self.client.get(reverse('perfil'))
        menu = {item['variante'] for item in response.context['menu_secoes']}
        self.assertIn('financeiro', menu)
        self.assertNotIn('compras', menu)
        self.assertNotIn('rock', menu)

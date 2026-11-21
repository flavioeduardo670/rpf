"""Novo visual: roleta da página inicial, boneco por seção e menu por permissão."""
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse

from core.context_processors import secao_por_caminho
from core.models import SlideInicio


class RoletaInicioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('admin', 'a@a.com', 'x')
        self.client.force_login(self.user)

    def test_sem_fotos_usa_ilustracoes_padrao(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'data-roleta')
        self.assertContains(response, 'core/roleta/casa.svg')
        self.assertContains(response, 'Portão dos Fundos')

    def test_fotos_cadastradas_substituem_as_padrao(self):
        gif = (b'GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff!\xf9\x04\x00\x00\x00\x00\x00'
               b',\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;')
        SlideInicio.objects.create(titulo='Fachada da casa', legenda='Nossa casa', imagem=SimpleUploadedFile('casa.gif', gif, 'image/gif'))
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'alt="Fachada da casa"')
        self.assertNotContains(response, 'core/roleta/casa.svg')


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
        self.assertContains(response, 'core/boneco/acao-compras-preto.svg')
        self.assertContains(response, 'rpf-transicao')  # cena da troca de página
        self.assertContains(response, 'corrida-compras.svg')  # mapa usado pela animação

    def test_todos_os_desenhos_existem(self):
        from pathlib import Path
        from django.conf import settings
        from core.context_processors import SECOES
        pasta = Path(settings.BASE_DIR) / 'core' / 'static' / 'core' / 'boneco'
        for variante in ['inicio'] + [s[1] for s in SECOES]:
            for nome in (f'acao-{variante}-preto.svg', f'icone-{variante}-branco.svg',
                         f'icone-{variante}-preto.svg', f'corrida-{variante}.svg'):
                self.assertTrue((pasta / nome).exists(), nome)


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

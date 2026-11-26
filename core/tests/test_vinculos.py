"""Usuários em uma ou mais organizações e a organização em uso em cada acesso."""
from django.conf import settings
from django.contrib.auth.models import User
from django.test import TestCase
from django.urls import reverse

from core.models import Organizacao, Vinculo
from core.organizacao_atual import desfazer, definir_organizacao


class UmaOrganizacaoTests(TestCase):
    """Como a Portão roda hoje: uma organização só."""

    def test_usuario_novo_entra_na_organizacao(self):
        user = User.objects.create_user('novo', password='x')
        self.assertEqual(list(user.vinculos.values_list('organizacao__nome', flat=True)), ['República Portão dos Fundos'])

    def test_login_mostra_a_marca_do_cliente(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, '<title>Entrar | República Portão dos Fundos</title>', html=False)

    def test_sem_seletor_de_organizacao(self):
        self.client.force_login(User.objects.create_user('ana', password='x'))
        self.assertNotContains(self.client.get(reverse('home')), 'trocar-organizacao')


class VariasOrganizacoesTests(TestCase):
    def setUp(self):
        self.portao = Organizacao.objects.get()
        self.verde = Organizacao.objects.create(
            nome='Casa Verde', nome_curto='CV', slug='casa-verde', segmento='moradia',
        )
        # Criados sem organização em uso: com duas ativas, ninguém é vinculado sozinho.
        self.ana = User.objects.create_user('ana', password='x')
        self.bia = User.objects.create_user('bia', password='x')
        Vinculo.objects.create(usuario=self.ana, organizacao=self.verde)
        Vinculo.objects.create(usuario=self.bia, organizacao=self.portao)
        Vinculo.objects.create(usuario=self.bia, organizacao=self.verde)

    def test_sem_organizacao_em_uso_usuario_novo_fica_sem_vinculo(self):
        self.assertFalse(User.objects.create_user('caio', password='x').vinculos.exists())

    def test_login_mostra_a_marca_do_produto(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, f'<title>Entrar | {settings.PRODUTO_NOME}</title>', html=False)
        self.assertNotContains(response, 'Portão dos Fundos')

    def test_cada_usuario_ve_a_sua_organizacao(self):
        self.client.force_login(self.ana)
        response = self.client.get(reverse('home'))
        self.assertContains(response, '| Casa Verde</title>', html=False)
        self.assertNotContains(response, 'trocar-organizacao')

    def test_quem_participa_de_duas_troca_de_organizacao(self):
        self.client.force_login(self.bia)
        response = self.client.get(reverse('home'))
        self.assertContains(response, '| República Portão dos Fundos</title>', html=False)
        self.assertContains(response, 'id="rpf-trocar-organizacao"', html=False)

        response = self.client.post(reverse('trocar_organizacao'), {'organizacao': self.verde.pk}, follow=True)
        self.assertContains(response, 'Agora você está em Casa Verde.')
        self.assertContains(response, '| Casa Verde</title>', html=False)

    def test_nao_troca_para_organizacao_de_que_nao_participa(self):
        self.client.force_login(self.ana)
        response = self.client.post(reverse('trocar_organizacao'), {'organizacao': self.portao.pk}, follow=True)
        self.assertContains(response, 'Você não participa dessa organização.')
        self.assertContains(response, '| Casa Verde</title>', html=False)

    def test_usuario_sem_vinculo_e_barrado_mas_consegue_sair(self):
        sem = User.objects.create_user('sem', password='x')
        self.client.force_login(sem)
        self.assertEqual(self.client.get(reverse('home')).status_code, 403)
        self.assertEqual(self.client.post(reverse('logout')).status_code, 302)

    def test_superusuario_pode_abrir_qualquer_organizacao(self):
        admin = User.objects.create_superuser('equipe', 'equipe@example.com', 'x')
        self.client.force_login(admin)
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'id="rpf-trocar-organizacao"', html=False)
        response = self.client.post(reverse('trocar_organizacao'), {'organizacao': self.verde.pk}, follow=True)
        self.assertContains(response, '| Casa Verde</title>', html=False)

    def test_organizacao_em_uso_vale_so_durante_o_acesso(self):
        self.client.force_login(self.ana)
        self.client.get(reverse('home'))
        # Fora de uma requisição, com duas ativas e nenhuma em uso: marca do produto.
        self.assertIsNone(Organizacao.atual().pk)

    def test_definir_organizacao_para_rotinas(self):
        token = definir_organizacao(self.verde)
        try:
            self.assertEqual(Organizacao.atual(), self.verde)
            caio = User.objects.create_user('caio', password='x')
            self.assertEqual(list(caio.vinculos.values_list('organizacao', flat=True)), [self.verde.pk])
        finally:
            desfazer(token)

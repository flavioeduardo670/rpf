from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.models import Morador, Setor


class PermissoesInsuficientesTests(TestCase):
    def setUp(self):
        self.sem_permissao = User.objects.create_user(username='sem_permissao', password='123456')

        self.financeiro_user = User.objects.create_user(username='financeiro', password='123456')
        financeiro_group, _ = Group.objects.get_or_create(name='Financeiro')
        self.financeiro_user.groups.add(financeiro_group)

        self.estoque_user = User.objects.create_user(username='estoque', password='123456')
        estoque_group, _ = Group.objects.get_or_create(name='Estoque')
        self.estoque_user.groups.add(estoque_group)
        self.setor = Setor.objects.create(nome='Estoque')

    def test_financeiro_requer_autenticacao(self):
        response = self.client.get(reverse('financeiro'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_financeiro_retorna_403_sem_permissao(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse('financeiro'))
        self.assertEqual(response.status_code, 403)

    def test_compras_retorna_403_sem_permissao(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse('compras'))
        self.assertEqual(response.status_code, 403)

    def test_almoxarifado_retorna_403_sem_permissao(self):
        self.client.force_login(self.sem_permissao)
        response = self.client.get(reverse('almoxarifado'))
        self.assertEqual(response.status_code, 403)

    def test_morador_com_visualizacao_nao_pode_editar(self):
        morador_user = User.objects.create_user(username='morador_visualizacao', password='123456')
        Morador.objects.create(
            nome='Morador Somente Visualizacao',
            user=morador_user,
            ativo=True,
            acesso_estoque_visualizar=True,
            acesso_estoque_editar=False,
        )
        self.client.force_login(morador_user)
        response = self.client.post(
            reverse('almoxarifado'),
            {
                'produto_submit': '1',
                'nome': 'Produto bloqueado',
                'descricao': 'Bem de Uso',
                'setor': self.setor.id,
                'quantidade': 1,
                'estoque_minimo': 0,
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_calendario_permite_visualizacao_com_permissao_de_leitura(self):
        user = User.objects.create_user(username='reunioes_visualizacao', password='123456')
        Morador.objects.create(
            nome='Morador Reunioes Leitura',
            user=user,
            ativo=True,
            acesso_reunioes_visualizar=True,
            acesso_reunioes_editar=False,
        )

        self.client.force_login(user)
        response = self.client.get(reverse('calendario'))
        self.assertEqual(response.status_code, 200)

    def test_calendario_bloqueia_post_sem_permissao_de_edicao(self):
        user = User.objects.create_user(username='reunioes_sem_edicao', password='123456')
        Morador.objects.create(
            nome='Morador Reunioes Somente Leitura',
            user=user,
            ativo=True,
            acesso_reunioes_visualizar=True,
            acesso_reunioes_editar=False,
        )

        self.client.force_login(user)
        response = self.client.post(reverse('calendario'), {'titulo': 'Reuniao geral', 'data': '2026-04-14'})
        self.assertEqual(response.status_code, 403)

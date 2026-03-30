from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings
from decimal import Decimal
import shutil
import tempfile

from .models import ConfiguracaoFinanceira, Morador, MovimentacaoEstoque, NotaFiscal, Produto, Setor


TEST_MEDIA_ROOT = tempfile.mkdtemp()


class PermissaoFinanceiroTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='financeiro', password='123456')
        group, _ = Group.objects.get_or_create(name='Financeiro')
        self.user.groups.add(group)
        self.nota = NotaFiscal.objects.create(
            setor='compras',
            descricao='Teste',
            fornecedor='Fornecedor',
            valor=100,
            data_emissao='2026-03-01',
            data_vencimento='2026-03-10',
            status='pendente',
        )

    def test_financeiro_requires_login(self):
        response = self.client.get(reverse('financeiro'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_financeiro_forbidden_without_permissao(self):
        sem_permissao = User.objects.create_user(username='sem_permissao', password='123456')
        self.client.force_login(sem_permissao)
        response = self.client.get(reverse('financeiro'))
        self.assertEqual(response.status_code, 403)

    def test_pagar_nota_requires_post(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('pagar_nota', args=[self.nota.id]))
        self.assertEqual(response.status_code, 405)

    def test_pagar_nota_por_post(self):
        self.client.force_login(self.user)
        response = self.client.post(reverse('pagar_nota', args=[self.nota.id]))
        self.assertEqual(response.status_code, 302)
        self.nota.refresh_from_db()
        self.assertEqual(self.nota.status, 'pago')
        self.assertIsNotNone(self.nota.data_pagamento)

    def test_exportar_financeiro_csv(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('exportar_financeiro_csv'))

        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('attachment; filename=\"financeiro_', response['Content-Disposition'])
        self.assertIn('Resumo Financeiro', response.content.decode('utf-8-sig'))

    def test_financeiro_salva_contas_fixas_por_post(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('financeiro'),
            {
                'valor_aluguel': '900.00',
                'valor_agua': '120.50',
                'valor_luz': '230.75',
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('financeiro'))
        config = ConfiguracaoFinanceira.objects.latest('id')
        self.assertEqual(config.valor_aluguel, Decimal('900.00'))
        self.assertEqual(config.valor_agua, Decimal('120.50'))
        self.assertEqual(config.valor_luz, Decimal('230.75'))


@override_settings(MEDIA_ROOT=TEST_MEDIA_ROOT)
class PerfilTests(TestCase):
    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        shutil.rmtree(TEST_MEDIA_ROOT, ignore_errors=True)

    def setUp(self):
        self.user = User.objects.create_user(username='perfil_user', password='123456')

    def test_perfil_requires_login(self):
        response = self.client.get(reverse('perfil'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_perfil_renderiza_dados_usuario(self):
        Morador.objects.create(nome='Perfil Morador', user=self.user, ativo=True, quarto='7')
        self.client.force_login(self.user)
        response = self.client.get(reverse('perfil'))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Perfil pessoal')
        self.assertContains(response, 'perfil_user')
        self.assertContains(response, 'Perfil Morador')

    def test_perfil_salva_foto(self):
        morador = Morador.objects.create(nome='Perfil Morador', user=self.user, ativo=True)
        self.client.force_login(self.user)
        upload = SimpleUploadedFile('foto.txt', b'conteudo-foto', content_type='text/plain')

        response = self.client.post(reverse('perfil'), {'foto_perfil': upload})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('perfil'))
        morador.refresh_from_db()
        self.assertTrue(bool(morador.foto_perfil))


class FinanceiroRateioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='financeiro_rateio', password='123456')
        group, _ = Group.objects.get_or_create(name='Financeiro')
        self.user.groups.add(group)

        ConfiguracaoFinanceira.objects.create(valor_aluguel=800, valor_agua=100, valor_luz=100)
        Morador.objects.create(nome='Ana', quarto='1', ativo=True)
        Morador.objects.create(nome='Bruno', quarto='2', ativo=True)
        Morador.objects.create(nome='Carlos', quarto='3', ativo=False)

        NotaFiscal.objects.create(
            setor='compras',
            descricao='Mercado',
            fornecedor='Fornecedor',
            valor=200,
            data_emissao='2026-03-01',
            data_vencimento='2026-03-10',
            status='pago',
        )
        NotaFiscal.objects.create(
            setor='compras',
            descricao='Internet',
            fornecedor='Fornecedor',
            valor=100,
            data_emissao='2026-03-01',
            data_vencimento='2026-03-10',
            status='pendente',
        )

    def test_financeiro_calcula_rateio_com_aluguel_e_gastos_pagos(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('financeiro'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['valor_aluguel'], Decimal('800'))
        self.assertEqual(response.context['valor_agua'], Decimal('100'))
        self.assertEqual(response.context['valor_luz'], Decimal('100'))
        self.assertEqual(response.context['total_despesas'], Decimal('200'))
        self.assertEqual(response.context['total_rateio'], Decimal('1200'))
        self.assertEqual(response.context['total_moradores_ativos'], 2)
        self.assertEqual(response.context['valor_por_morador'], Decimal('600.00'))
        self.assertEqual(len(response.context['rateio_moradores']), 2)


class EstoqueTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='estoque', password='123456')
        group, _ = Group.objects.get_or_create(name='Estoque')
        self.user.groups.add(group)
        self.setor = Setor.objects.create(nome='Estoque')
        self.produto = Produto.objects.create(
            nome='Parafuso',
            descricao='Aco',
            setor=self.setor,
            quantidade=2,
            estoque_minimo=1,
        )

    def test_bloqueia_saida_maior_que_estoque(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('almoxarifado'),
            {
                'movimentacao_submit': '1',
                'produto': self.produto.id,
                'tipo': 'saida',
                'quantidade': 3,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.produto.refresh_from_db()
        self.assertEqual(self.produto.quantidade, 2)
        self.assertEqual(MovimentacaoEstoque.objects.count(), 0)

    def test_cadastra_produto_com_setor(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('almoxarifado'),
            {
                'produto_submit': '1',
                'nome': 'Martelo',
                'descricao': 'Ferramenta',
                'setor': self.setor.id,
                'local': '',
                'quantidade': 5,
                'estoque_minimo': 1,
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Produto.objects.filter(nome='Martelo').exists())


class AdminUserVinculoTests(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_superuser(
            username='admin',
            email='admin@test.com',
            password='Admin123..',
        )
        self.morador = Morador.objects.create(nome='Joao da Casa', ativo=True)

    def test_admin_cria_usuario_com_morador(self):
        self.client.force_login(self.admin_user)
        response = self.client.post(
            reverse('admin:auth_user_add'),
            {
                'username': 'novo_usuario',
                'password1': 'SenhaForte123..',
                'password2': 'SenhaForte123..',
                'morador': str(self.morador.id),
                '_save': 'Salvar',
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        novo_usuario = User.objects.get(username='novo_usuario')
        self.morador.refresh_from_db()
        self.assertEqual(self.morador.user_id, novo_usuario.id)

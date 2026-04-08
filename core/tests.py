from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.test.utils import override_settings
from django.utils import timezone
from decimal import Decimal
from io import BytesIO
from PIL import Image
import shutil
import tempfile

from .models import (
    ConfiguracaoFinanceira,
    Morador,
    MovimentacaoEstoque,
    NotaFiscal,
    NotaParcela,
    Produto,
    Setor,
)


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

    @staticmethod
    def _build_test_image_bytes():
        imagem = Image.new('RGB', (1, 1), color='white')
        stream = BytesIO()
        imagem.save(stream, format='PNG')
        return stream.getvalue()

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
        imagem_png_1x1 = self._build_test_image_bytes()
        upload = SimpleUploadedFile('foto.png', imagem_png_1x1, content_type='image/png')

        response = self.client.post(reverse('perfil'), {'foto_perfil': upload})

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('perfil'))
        morador.refresh_from_db()
        self.assertTrue(bool(morador.foto_perfil))

    def test_perfil_bloqueia_extensoes_nao_permitidas(self):
        morador = Morador.objects.create(nome='Perfil Morador', user=self.user, ativo=True)
        self.client.force_login(self.user)

        imagem_png_1x1 = self._build_test_image_bytes()
        upload_txt = SimpleUploadedFile('arquivo.txt', imagem_png_1x1, content_type='image/png')
        response_txt = self.client.post(reverse('perfil'), {'foto_perfil': upload_txt})
        self.assertEqual(response_txt.status_code, 200)
        self.assertContains(response_txt, 'Nao foi possivel salvar a foto')

        upload_exe = SimpleUploadedFile('arquivo.exe', imagem_png_1x1, content_type='image/png')
        response_exe = self.client.post(reverse('perfil'), {'foto_perfil': upload_exe})
        self.assertEqual(response_exe.status_code, 200)
        self.assertContains(response_exe, 'Nao foi possivel salvar a foto')

        morador.refresh_from_db()
        self.assertFalse(bool(morador.foto_perfil))


class FinanceiroRateioTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='financeiro_rateio', password='123456')
        group, _ = Group.objects.get_or_create(name='Financeiro')
        self.user.groups.add(group)

        Morador.objects.all().delete()
        self.mes_referencia = timezone.localdate().replace(day=1)
        ConfiguracaoFinanceira.objects.create(valor_aluguel=800, valor_agua=100, valor_luz=100)
        Morador.objects.create(nome='Ana', quarto='1', ativo=True)
        Morador.objects.create(nome='Bruno', quarto='2', ativo=True)
        Morador.objects.create(nome='Carlos', quarto='3', ativo=False)

        nota_paga = NotaFiscal.objects.create(
            setor='compras',
            descricao='Mercado',
            fornecedor='Fornecedor',
            valor=200,
            data_emissao=self.mes_referencia,
            data_vencimento=self.mes_referencia.replace(day=10),
            status='pago',
            tipo_item='Bem Material',
        )
        NotaParcela.objects.create(
            nota=nota_paga,
            numero=1,
            valor=200,
            vencimento=self.mes_referencia.replace(day=10),
            mes_referencia=self.mes_referencia,
            status='pago',
        )

        nota_pendente = NotaFiscal.objects.create(
            setor='compras',
            descricao='Internet',
            fornecedor='Fornecedor',
            valor=100,
            data_emissao=self.mes_referencia,
            data_vencimento=self.mes_referencia.replace(day=15),
            status='pendente',
            tipo_item='Bem de Consumo',
        )
        NotaParcela.objects.create(
            nota=nota_pendente,
            numero=1,
            valor=100,
            vencimento=self.mes_referencia.replace(day=15),
            mes_referencia=self.mes_referencia,
            status='pendente',
        )

    def test_financeiro_calcula_rateio_com_aluguel_e_gastos_pagos(self):
        self.client.force_login(self.user)
        response = self.client.get(f"{reverse('financeiro')}?mes={self.mes_referencia.strftime('%Y-%m')}")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['valor_aluguel'], Decimal('800'))
        self.assertEqual(response.context['total_despesas'], Decimal('200'))
        self.assertEqual(response.context['total_rateio'], Decimal('1100.00'))
        self.assertEqual(response.context['total_moradores_ativos'], 2)
        self.assertEqual(response.context['valor_por_morador'], Decimal('550.00'))
        self.assertEqual(len(response.context['rateio_moradores']), 2)


class MoradoresEdicaoTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='moradores_editor', password='123456')
        self.morador = Morador.objects.create(
            nome='Morador Teste',
            apelido='MT',
            email='morador@teste.com',
            codigo_quarto='Q1',
            quarto='1',
            ativo=True,
        )

    def test_moradores_renderiza_colunas_novas_sem_peso(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('moradores'))
        self.assertContains(response, 'Curso')
        self.assertContains(response, 'Funções')
        self.assertNotContains(response, 'Peso')

    def test_moradores_salva_curso_e_funcoes(self):
        self.client.force_login(self.user)
        response = self.client.post(
            reverse('moradores'),
            {
                'form-TOTAL_FORMS': '1',
                'form-INITIAL_FORMS': '1',
                'form-MIN_NUM_FORMS': '0',
                'form-MAX_NUM_FORMS': '1000',
                'form-0-id': str(self.morador.id),
                'form-0-ordem_hierarquia': '0',
                'form-0-nome': 'Morador Teste',
                'form-0-apelido': 'MT',
                'form-0-email': 'morador@teste.com',
                'form-0-codigo_quarto': 'Q1',
                'form-0-quarto': '1',
                'form-0-curso': 'Engenharia',
                'form-0-funcoes': 'Compras e Infraestrutura',
                'form-0-ativo': 'on',
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.url, reverse('moradores'))
        self.morador.refresh_from_db()
        self.assertEqual(self.morador.curso, 'Engenharia')
        self.assertEqual(self.morador.funcoes, 'Compras e Infraestrutura')


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


class CadastroPublicoTests(TestCase):
    def test_usuario_anonimo_nao_consegue_criar_conta_via_cadastro(self):
        total_antes = User.objects.count()

        response = self.client.post(
            '/cadastro/',
            {
                'username': 'novo_usuario',
                'password1': 'SenhaSegura@123',
                'password2': 'SenhaSegura@123',
            },
        )

        self.assertEqual(response.status_code, 404)
        self.assertEqual(User.objects.count(), total_antes)


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


class MigracaoViewsPorDominioRoutesTests(TestCase):
    def setUp(self):
        self.financeiro_user = User.objects.create_user(username='financeiro_migracao', password='123456')
        financeiro_group, _ = Group.objects.get_or_create(name='Financeiro')
        self.financeiro_user.groups.add(financeiro_group)

        self.estoque_user = User.objects.create_user(username='estoque_migracao', password='123456')
        estoque_group, _ = Group.objects.get_or_create(name='Estoque')
        self.estoque_user.groups.add(estoque_group)

        self.rock_user = User.objects.create_user(username='rock_migracao', password='123456')
        rock_group, _ = Group.objects.get_or_create(name='Rock')
        self.rock_user.groups.add(rock_group)

        self.admin_user = User.objects.create_superuser(
            username='admin_migracao',
            email='admin_migracao@test.com',
            password='Admin123..',
        )
        self.sem_permissao = User.objects.create_user(username='sem_permissao_migracao', password='123456')

        self.nota = NotaFiscal.objects.create(
            setor='compras',
            descricao='Conta de internet',
            fornecedor='Fornecedor Teste',
            valor=Decimal('150.00'),
            data_emissao='2026-03-01',
            data_vencimento='2026-03-10',
            status='pendente',
        )
        self.parcela = NotaParcela.objects.create(
            nota=self.nota,
            numero=1,
            valor=Decimal('150.00'),
            vencimento='2026-03-10',
            mes_referencia='2026-03-01',
            status='pendente',
        )

    def test_fluxo_pagamento_critico_por_rotas_migradas(self):
        self.client.force_login(self.financeiro_user)

        financeiro_response = self.client.get(reverse('financeiro'))
        self.assertEqual(financeiro_response.status_code, 200)

        pagar_nota_response = self.client.post(reverse('pagar_nota', args=[self.nota.id]))
        self.assertEqual(pagar_nota_response.status_code, 302)

        self.parcela.status = 'pendente'
        self.parcela.data_pagamento = None
        self.parcela.save(update_fields=['status', 'data_pagamento'])

        pagar_parcela_response = self.client.post(reverse('pagar_parcela', args=[self.parcela.id]))
        self.assertEqual(pagar_parcela_response.status_code, 302)

        self.nota.refresh_from_db()
        self.parcela.refresh_from_db()
        self.assertEqual(self.nota.status, 'pago')
        self.assertEqual(self.parcela.status, 'pago')

    def test_regressao_permissoes_acessos(self):
        self.client.force_login(self.sem_permissao)
        forbidden = self.client.get(reverse('gerenciar_acessos'))
        self.assertEqual(forbidden.status_code, 403)

        self.client.force_login(self.admin_user)
        allowed = self.client.get(reverse('gerenciar_acessos'))
        self.assertEqual(allowed.status_code, 200)

    def test_regressao_rotas_moradores_e_rock(self):
        self.client.force_login(self.admin_user)
        moradores_response = self.client.get(reverse('moradores'))
        self.assertEqual(moradores_response.status_code, 200)

        self.client.force_login(self.rock_user)
        rock_response = self.client.get(reverse('rock'))
        self.assertEqual(rock_response.status_code, 200)

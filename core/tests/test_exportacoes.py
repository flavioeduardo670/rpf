from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.models import NotaFiscal, Setor, Produto


class ExportacoesTests(TestCase):
    def setUp(self):
        self.financeiro_user = User.objects.create_user(username='financeiro_export', password='123456')
        financeiro_group, _ = Group.objects.get_or_create(name='Financeiro')
        self.financeiro_user.groups.add(financeiro_group)

        self.compras_user = User.objects.create_user(username='compras_export', password='123456')
        compras_group, _ = Group.objects.get_or_create(name='Compras')
        self.compras_user.groups.add(compras_group)

        self.estoque_user = User.objects.create_user(username='estoque_export', password='123456')
        estoque_group, _ = Group.objects.get_or_create(name='Estoque')
        self.estoque_user.groups.add(estoque_group)

        self.setor = Setor.objects.create(nome='Estoque')
        Produto.objects.create(nome='Parafuso', descricao='Bem de Uso', setor=self.setor, quantidade=10, estoque_minimo=2)
        NotaFiscal.objects.create(
            setor='compras',
            descricao='Compra de teste',
            fornecedor='Fornecedor Teste',
            valor=Decimal('120.00'),
            data_emissao='2026-04-01',
            data_vencimento='2026-04-10',
            status='pendente',
            quantidade=1,
            tipo_item='Bem Material',
        )

    def test_exportar_financeiro_csv(self):
        self.client.force_login(self.financeiro_user)
        response = self.client.get(reverse('exportar_financeiro_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('text/csv', response['Content-Type'])
        self.assertIn('Resumo Financeiro', response.content.decode('utf-8-sig'))

    def test_exportar_compras_csv(self):
        self.client.force_login(self.compras_user)
        response = self.client.get(reverse('exportar_compras_csv'))
        self.assertEqual(response.status_code, 200)
        self.assertIn('Notas de Compras', response.content.decode('utf-8-sig'))

    def test_exportar_estoque_csv(self):
        self.client.force_login(self.estoque_user)
        response = self.client.get(reverse('exportar_estoque_csv'))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode('utf-8-sig')
        self.assertIn('Estoque do Almoxarifado', body)
        self.assertIn('Parafuso', body)

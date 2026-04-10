from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase
from django.urls import reverse

from core.models import AjusteMorador, Morador, PendenciaMensalItem


class FinanceiroTemplateTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='financeiro_template', password='123456')
        financeiro_group, _ = Group.objects.get_or_create(name='Financeiro')
        self.user.groups.add(financeiro_group)
        self.client.force_login(self.user)

        self.mes = date(2026, 5, 1)
        self.morador = Morador.objects.create(nome='Morador Teste', ativo=True)

        self.ajuste = AjusteMorador.objects.create(
            morador=self.morador,
            mes_referencia=self.mes,
            tipo='extra',
            valor=Decimal('123.45'),
            motivo='Extra de teste',
        )
        self.pendencia = PendenciaMensalItem.objects.create(
            mes_referencia=self.mes,
            tipo='extra',
            valor=Decimal('54.32'),
            motivo='Pendência de teste',
        )

    def test_financeiro_exibe_campos_hidden_para_exclusao_de_ajustes_e_pendencias(self):
        response = self.client.get(reverse('financeiro') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)

        html = response.content.decode('utf-8')
        self.assertIn(f'name="ajuste-0-id" value="{self.ajuste.id}"', html)
        self.assertIn(f'name="pendencia-0-id" value="{self.pendencia.id}"', html)

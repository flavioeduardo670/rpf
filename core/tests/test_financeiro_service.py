from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from core.models import DescontoMensal, PendenciaMensal
from core.services.financeiro import calcular_rateio_financeiro, resolver_mes_referencia


class ResolverMesReferenciaTests(SimpleTestCase):
    def test_retorna_mes_atual_ate_dia_10(self):
        with patch('core.services.financeiro.timezone.localdate', return_value=date(2026, 4, 10)):
            self.assertEqual(resolver_mes_referencia(None), date(2026, 4, 1))

    def test_retorna_proximo_mes_a_partir_do_dia_11(self):
        with patch('core.services.financeiro.timezone.localdate', return_value=date(2026, 4, 11)):
            self.assertEqual(resolver_mes_referencia(None), date(2026, 5, 1))

    def test_prioriza_mes_param_quando_informado(self):
        with patch('core.services.financeiro.timezone.localdate', return_value=date(2026, 4, 30)):
            self.assertEqual(resolver_mes_referencia('2026-02'), date(2026, 2, 1))


class CalcularRateioFinanceiroTests(TestCase):
    def test_ignora_tabelas_legadas_de_desconto_e_pendencia_sem_itens_no_mes(self):
        mes = date(2026, 5, 1)
        DescontoMensal.objects.create(mes_referencia=mes, valor_total=Decimal('100.00'))
        PendenciaMensal.objects.create(mes_referencia=mes, valor_total=Decimal('123.28'))

        resumo = calcular_rateio_financeiro(mes, incluir_pendencia=True)

        self.assertEqual(resumo['desconto_total_mes'], Decimal('0.00'))
        self.assertEqual(resumo['pendencia_total_mes'], Decimal('0.00'))
        self.assertEqual(resumo['pendencia_por_morador'], Decimal('0.00'))

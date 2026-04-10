from datetime import date
from unittest.mock import patch

from django.test import SimpleTestCase

from core.services.financeiro import resolver_mes_referencia


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

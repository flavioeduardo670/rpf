from datetime import date

from django.test import TestCase

from core.forms import EventoCalendarioForm
from core.models import EventoCalendario, NotaFiscal
from core.views.financeiro import NotaFiscalForm


class DateFieldEdicaoTests(TestCase):
    def test_evento_calendario_mantem_valor_data_no_formulario_de_edicao(self):
        evento = EventoCalendario.objects.create(titulo='Reunião geral', data=date(2026, 4, 15))
        form = EventoCalendarioForm(instance=evento)

        html = form['data'].as_widget()
        self.assertIn('value="2026-04-15"', html)

    def test_nota_fiscal_mantem_datas_no_formulario_de_edicao(self):
        nota = NotaFiscal.objects.create(
            descricao='Compra teste',
            fornecedor='Fornecedor X',
            valor='10.00',
            data_emissao=date(2026, 4, 10),
            data_vencimento=date(2026, 4, 20),
            data_pagamento=date(2026, 4, 21),
            quantidade=1,
            tipo_item='Bem de Uso',
        )
        form = NotaFiscalForm(instance=nota)

        self.assertIn('value="2026-04-10"', form['data_emissao'].as_widget())
        self.assertIn('value="2026-04-20"', form['data_vencimento'].as_widget())
        self.assertIn('value="2026-04-21"', form['data_pagamento'].as_widget())

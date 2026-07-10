from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase, TestCase

from core.models import DescontoMensal, PendenciaMensal
from core.models import ContaCasa, Morador, NotaFiscal, NotaParcela
from core.services.financeiro import calcular_rateio_financeiro, resolver_mes_referencia, salvar_registro_financeiro_mensal


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

    def test_rateia_parcela_mesmo_com_tipo_item_customizado(self):
        mes = date(2026, 5, 1)
        Morador.objects.create(nome='Morador 1', ativo=True, peso_quarto=Decimal('1.0'))
        Morador.objects.create(nome='Morador 2', ativo=True, peso_quarto=Decimal('1.0'))
        nota = NotaFiscal.objects.create(
            setor='compras',
            descricao='Compra X',
            fornecedor='Fornecedor',
            tipo_item='bem_consumo',
            quantidade=1,
            valor=Decimal('200.00'),
            cobrar_no_aluguel=True,
            data_emissao=date(2026, 4, 2),
            data_vencimento=date(2026, 4, 10),
            status='pendente',
        )
        NotaParcela.objects.create(
            nota=nota,
            numero=1,
            valor=Decimal('200.00'),
            vencimento=date(2026, 5, 5),
            mes_referencia=mes,
            status='pendente',
        )

        resumo = calcular_rateio_financeiro(mes, incluir_pendencia=True)

        self.assertEqual(resumo['total_parcelas_mes_rateio'], Decimal('200.00'))
        self.assertEqual(resumo['caixinha_por_morador'], Decimal('100.00'))

    def test_categoria_rock_entra_no_rateio_quando_cobrar_no_aluguel_ativo(self):
        mes = date(2026, 5, 1)
        Morador.objects.create(nome='Morador 1', ativo=True, peso_quarto=Decimal('1.0'))
        Morador.objects.create(nome='Morador 2', ativo=True, peso_quarto=Decimal('1.0'))
        nota = NotaFiscal.objects.create(
            setor='compras',
            descricao='Compra Rock',
            fornecedor='Fornecedor',
            categoria_compra='rock',
            tipo_item='Bem de Consumo',
            quantidade=1,
            valor=Decimal('80.00'),
            cobrar_no_aluguel=True,
            data_emissao=date(2026, 4, 2),
            data_vencimento=date(2026, 4, 10),
            status='pendente',
        )
        NotaParcela.objects.create(
            nota=nota,
            numero=1,
            valor=Decimal('80.00'),
            vencimento=date(2026, 5, 5),
            mes_referencia=mes,
            status='pendente',
        )

        resumo = calcular_rateio_financeiro(mes, incluir_pendencia=True)

        self.assertEqual(resumo['total_parcelas_mes_rateio'], Decimal('80.00'))
        self.assertEqual(resumo['caixinha_por_morador'], Decimal('40.00'))

    def test_nota_nao_entra_no_rateio_quando_cobrar_no_aluguel_desativado(self):
        mes = date(2026, 5, 1)
        Morador.objects.create(nome='Morador 1', ativo=True, peso_quarto=Decimal('1.0'))
        Morador.objects.create(nome='Morador 2', ativo=True, peso_quarto=Decimal('1.0'))
        nota = NotaFiscal.objects.create(
            setor='compras',
            descricao='Compra sem rateio',
            fornecedor='Fornecedor',
            categoria_compra='rock',
            tipo_item='Bem de Consumo',
            quantidade=1,
            valor=Decimal('90.00'),
            cobrar_no_aluguel=False,
            data_emissao=date(2026, 4, 2),
            data_vencimento=date(2026, 4, 10),
            status='pendente',
        )
        NotaParcela.objects.create(
            nota=nota,
            numero=1,
            valor=Decimal('90.00'),
            vencimento=date(2026, 5, 5),
            mes_referencia=mes,
            status='pendente',
        )

        resumo = calcular_rateio_financeiro(mes, incluir_pendencia=True)

        self.assertEqual(resumo['total_parcelas_mes_rateio'], Decimal('0.00'))
        self.assertEqual(resumo['caixinha_por_morador'], Decimal('0.00'))

    def test_conta_da_casa_recorrente_entra_nos_meses_futuros(self):
        maio = date(2026, 5, 1)
        junho = date(2026, 6, 1)
        Morador.objects.create(nome='Morador 1', ativo=True, peso_quarto=Decimal('1.0'))
        Morador.objects.create(nome='Morador 2', ativo=True, peso_quarto=Decimal('1.0'))
        ContaCasa.objects.create(
            nome='Energia',
            valor=Decimal('100.00'),
            data_vencimento=date(2026, 5, 15),
            mes_cobranca_aluguel=maio,
            forma_pagamento='PIX',
            repetir_meses_futuros=True,
            ativo=True,
        )

        resumo_maio = calcular_rateio_financeiro(maio, incluir_pendencia=True)
        resumo_junho = calcular_rateio_financeiro(junho, incluir_pendencia=True)

        self.assertEqual(resumo_maio['valor_fixas_total'], Decimal('100.00'))
        self.assertEqual(resumo_junho['valor_fixas_total'], Decimal('100.00'))
        self.assertEqual(resumo_junho['contas_fixas'][0].vencimento_rateio, date(2026, 6, 15))

    def test_conta_da_casa_nao_recorrente_nao_entra_em_outros_meses(self):
        maio = date(2026, 5, 1)
        junho = date(2026, 6, 1)
        ContaCasa.objects.create(
            nome='Internet',
            valor=Decimal('80.00'),
            data_vencimento=date(2026, 5, 20),
            mes_cobranca_aluguel=maio,
            repetir_meses_futuros=False,
            ativo=True,
        )

        self.assertEqual(calcular_rateio_financeiro(maio, incluir_pendencia=True)['valor_fixas_total'], Decimal('80.00'))
        self.assertEqual(calcular_rateio_financeiro(junho, incluir_pendencia=True)['valor_fixas_total'], Decimal('0.00'))


    def test_registro_salvo_preserva_morador_desativado_depois(self):
        mes = date(2026, 5, 1)
        morador_antigo = Morador.objects.create(nome='Morador Antigo', apelido='Antigo', ativo=True, peso_quarto=Decimal('1.0'))
        Morador.objects.create(nome='Morador Atual', apelido='Atual', ativo=True, peso_quarto=Decimal('1.0'))

        registro = salvar_registro_financeiro_mensal(mes)
        morador_antigo.ativo = False
        morador_antigo.save(update_fields=['ativo'])

        registro.refresh_from_db()
        self.assertEqual(registro.moradores.count(), 2)
        self.assertTrue(registro.moradores.filter(morador_apelido='Antigo').exists())
        self.assertEqual(calcular_rateio_financeiro(mes, incluir_pendencia=True)['total_moradores_ativos'], 1)


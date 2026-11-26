"""Dois clientes no mesmo sistema: nenhum enxerga ou altera dados do outro."""
import json
from datetime import date
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.core.exceptions import ValidationError
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    CobrancaAluguel, DescontoMensal, IngressoRock, Mensalidade, Morador, NotaFiscal, Organizacao,
    RockEvento, Vinculo,
)
from core.organizacao_atual import definir_organizacao, desfazer
from core.views.common import get_user_morador


class DoisClientes(TestCase):
    def setUp(self):
        self.portao = Organizacao.objects.get()
        self.verde = Organizacao.objects.create(nome='Casa Verde', nome_curto='CV', slug='casa-verde', segmento='moradia')
        financeiro = Group.objects.get_or_create(name='Financeiro')[0]
        compras = Group.objects.get_or_create(name='Compras')[0]

        self.ana = User.objects.create_user('ana', password='x')  # Portão
        self.bia = User.objects.create_user('bia', password='x')  # Casa Verde
        for user, org in ((self.ana, self.portao), (self.bia, self.verde)):
            Vinculo.objects.create(usuario=user, organizacao=org)
            user.groups.add(financeiro, compras)

        with self.na(self.portao):
            self.morador_portao = Morador.objects.create(nome='Morador da Portão', user=self.ana, ativo=True)
            self.nota_portao = NotaFiscal.objects.create(
                descricao='Gás Portão', fornecedor='F', valor=Decimal('10'), data_emissao=date(2026, 5, 1),
                data_vencimento=date(2026, 5, 1), setor='compras',
            )
        with self.na(self.verde):
            self.morador_verde = Morador.objects.create(nome='Morador da Verde', user=self.bia, ativo=True)
            self.nota_verde = NotaFiscal.objects.create(
                descricao='Gás Verde', fornecedor='F', valor=Decimal('20'), data_emissao=date(2026, 5, 1),
                data_vencimento=date(2026, 5, 1), setor='compras',
            )

    class na:
        """with self.na(org): age em nome da organização (como num acesso dela)."""

        def __init__(self, org):
            self.org = org

        def __enter__(self):
            self.token = definir_organizacao(self.org)

        def __exit__(self, *exc):
            desfazer(self.token)


class ConsultasFiltradasTests(DoisClientes):
    def test_cada_organizacao_so_ve_os_proprios_registros(self):
        with self.na(self.portao):
            self.assertEqual(list(Morador.objects.values_list('nome', flat=True)), ['Morador da Portão'])
            self.assertEqual(NotaFiscal.objects.count(), 1)
        with self.na(self.verde):
            self.assertEqual(list(Morador.objects.values_list('nome', flat=True)), ['Morador da Verde'])
        # Fora de um acesso (comandos, webhooks) e na visão da plataforma: tudo.
        self.assertEqual(Morador.objects.count(), 2)
        self.assertEqual(Morador.todas_as_organizacoes.count(), 2)

    def test_registro_novo_herda_a_organizacao(self):
        self.assertEqual(self.morador_verde.organizacao, self.verde)
        # Sem acesso em andamento (ex.: webhook): herda do registro "pai".
        mensalidade = Mensalidade.objects.create(morador=self.morador_verde, mes_referencia=date(2026, 5, 1), valor=1)
        self.assertEqual(mensalidade.organizacao, self.verde)
        # Criação em lote também.
        with self.na(self.verde):
            evento = RockEvento.objects.create(nome='Festa', tipo='nosso', data=date(2026, 5, 2))
        IngressoRock.objects.bulk_create([IngressoRock(rock_evento=evento, nome='X', quantidade_ingressos=1, valor_unitario=1)])
        self.assertEqual(IngressoRock.objects.get().organizacao, self.verde)

    def test_sem_como_saber_a_organizacao_recusa_salvar(self):
        with self.assertRaises(ValueError):
            RockEvento.objects.create(nome='Órfão', tipo='nosso', data=date(2026, 5, 2))

    def test_regras_de_unico_valem_por_organizacao(self):
        with self.na(self.portao):
            DescontoMensal.objects.create(mes_referencia=date(2026, 5, 1))
            repetido = DescontoMensal(mes_referencia=date(2026, 5, 1))
            with self.assertRaises(ValidationError):
                repetido.validate_unique()
        with self.na(self.verde):
            DescontoMensal.objects.create(mes_referencia=date(2026, 5, 1))  # mesmo mês, outro cliente: ok
        self.assertEqual(DescontoMensal.objects.count(), 2)

    def test_formulario_montado_ao_iniciar_o_sistema_filtra_por_organizacao(self):
        from core.forms import AjusteMoradorForm

        # A lista do campo foi montada sem organização (ao importar o módulo)...
        self.assertEqual(AjusteMoradorForm.base_fields['morador'].queryset.count(), 2)
        # ...mas cada formulário criado num acesso só oferece os membros daquela organização.
        with self.na(self.verde):
            opcoes = list(AjusteMoradorForm().fields['morador'].queryset.values_list('nome', flat=True))
        self.assertEqual(opcoes, ['Morador da Verde'])

    def test_mesmo_login_pode_ser_membro_em_cada_organizacao(self):
        Vinculo.objects.create(usuario=self.ana, organizacao=self.verde)
        with self.na(self.verde):
            outro = Morador.objects.create(nome='Ana na Verde', user=self.ana)
            self.assertEqual(get_user_morador(User.objects.get(pk=self.ana.pk)), outro)
        with self.na(self.portao):
            self.assertEqual(get_user_morador(User.objects.get(pk=self.ana.pk)), self.morador_portao)


class TelasIsoladasTests(DoisClientes):
    def test_lista_de_membros_so_da_propria_organizacao(self):
        self.client.force_login(self.ana)
        response = self.client.get(reverse('moradores'))
        self.assertContains(response, 'Morador da Portão')
        self.assertNotContains(response, 'Morador da Verde')

    def test_nao_abre_registro_de_outra_organizacao_pelo_endereco(self):
        self.client.force_login(self.ana)
        self.assertEqual(self.client.get(reverse('editar_nota_compra', args=[self.nota_verde.pk])).status_code, 404)
        self.assertEqual(self.client.get(reverse('editar_nota_compra', args=[self.nota_portao.pk])).status_code, 200)
        extrato_alheio = self.client.get(reverse('financeiro_prestacao_contas_morador', args=[self.morador_verde.pk]))
        self.assertIn(extrato_alheio.status_code, (403, 404))

    def test_nao_altera_registro_de_outra_organizacao(self):
        self.client.force_login(self.ana)
        self.client.post(reverse('editar_nota_compra', args=[self.nota_verde.pk]), {'excluir_submit': '1'})
        self.assertTrue(NotaFiscal.objects.filter(pk=self.nota_verde.pk).exists())

    def test_listas_de_selecao_dos_formularios_so_com_a_propria_organizacao(self):
        self.client.force_login(self.bia)
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Morador da Verde')
        self.assertNotContains(response, 'Morador da Portão')
        self.assertNotContains(response, 'Gás Portão')

    def test_exportacao_so_com_a_propria_organizacao(self):
        self.client.force_login(self.bia)
        conteudo = self.client.get(reverse('exportar_compras_csv')).content.decode('utf-8')
        self.assertIn('Gás Verde', conteudo)
        self.assertNotIn('Gás Portão', conteudo)


@override_settings(MERCADOPAGO_WEBHOOK_SECRET='', DEBUG=True)
class WebhookComDoisClientesTests(DoisClientes):
    def setUp(self):
        super().setUp()
        with self.na(self.verde):
            self.cobranca = CobrancaAluguel.objects.create(
                morador=self.morador_verde, mes_referencia=date(2026, 5, 1), valor=Decimal('100'),
                txid='RPFALVERDE1', status='aguardando_pagamento',
            )

    def _avisar(self, url):
        return self.client.post(
            url, data=json.dumps({'txid': 'RPFALVERDE1', 'status': 'approved'}), content_type='application/json',
        )

    def test_webhook_no_endereco_do_cliente_confirma_a_cobranca_dele(self):
        response = self._avisar(reverse('webhook_pix_organizacao', args=['casa-verde']))
        self.assertEqual(response.status_code, 200)
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'pago')
        self.assertEqual(Mensalidade.objects.get(morador=self.morador_verde).organizacao, self.verde)

    def test_webhook_de_outro_cliente_nao_confirma(self):
        # Endereço antigo (sem cliente) é da Portão: não enxerga a cobrança da Casa Verde.
        response = self._avisar(reverse('webhook_pix_financeiro'))
        self.assertJSONEqual(response.content, {'ok': True, 'detail': 'pagamento_nao_encontrado'})
        self.cobranca.refresh_from_db()
        self.assertEqual(self.cobranca.status, 'aguardando_pagamento')

    def test_webhook_de_cliente_desconhecido_responde_404(self):
        self.assertEqual(self._avisar(reverse('webhook_pix_organizacao', args=['nao-existe'])).status_code, 404)

"""Mercado Pago, email e rotinas por organização (passo 5c)."""
import hashlib
import hmac
import importlib
import json
from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import MagicMock, patch

from django.apps import apps as django_apps
from django.core import mail
from django.core.management import call_command
from django.test import SimpleTestCase, TestCase, override_settings
from django.urls import reverse

from core.admin import OrganizacaoAdminForm
from core.credenciais import cifrar, decifrar, mascarar
from core.models import CobrancaAluguel, Morador, NotificacaoMorador, Organizacao
from core.organizacao_atual import na_organizacao
from core.services.aluguel import verificar_pagamentos_pendentes
from core.services.pix_gateway import credenciais_mercado_pago, criar_cobranca_pix_avulsa, url_notificacao_mercado_pago
from core.views.financeiro import enviar_comprovante_aluguel_por_email


class CifragemTests(SimpleTestCase):
    def test_ida_e_volta_e_mascara(self):
        cifrado = cifrar('APP_USR-1234567890-abcdef')
        self.assertNotIn('APP_USR', cifrado)
        self.assertEqual(decifrar(cifrado), 'APP_USR-1234567890-abcdef')
        self.assertEqual(mascarar('APP_USR-1234567890-abcdef'), 'APP_USR-…cdef')
        self.assertEqual(cifrar(''), '')

    def test_chave_diferente_nao_le(self):
        cifrado = cifrar('segredo')
        with override_settings(CREDENCIAIS_CHAVE='3q2-7wEXAMPLEKEYexampleKEY1234567890abcdEFG='):
            self.assertEqual(decifrar(cifrado), '')


class UmClienteSoTests(TestCase):
    """A Portão hoje: credenciais do servidor continuam valendo."""

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='Bearer TOKEN-SERVIDOR', MERCADOPAGO_WEBHOOK_SECRET='seg-servidor')
    def test_sem_token_proprio_usa_o_do_servidor(self):
        _org, token, segredo = credenciais_mercado_pago()
        self.assertEqual((token, segredo), ('TOKEN-SERVIDOR', 'seg-servidor'))

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='TOKEN-SERVIDOR')
    def test_token_da_organizacao_tem_prioridade(self):
        org = Organizacao.objects.get()
        org.mercadopago_access_token = 'TOKEN-PORTAO'
        org.save()
        self.assertEqual(credenciais_mercado_pago()[1], 'TOKEN-PORTAO')

    @override_settings(MERCADOPAGO_ACCESS_TOKEN='Bearer APP_USR-da-portao', MERCADOPAGO_WEBHOOK_SECRET='seg-portao')
    def test_migracao_leva_as_credenciais_do_servidor_para_a_portao(self):
        Organizacao.objects.update(mercadopago_access_token_cifrado='', mercadopago_webhook_secret_cifrado='')
        migracao = importlib.import_module('core.migrations.0077_credenciais_por_organizacao')
        migracao.credenciais_do_servidor_para_a_primeira_organizacao(django_apps, None)
        org = Organizacao.objects.get()
        self.assertEqual(org.mercadopago_access_token, 'APP_USR-da-portao')
        self.assertEqual(org.mercadopago_webhook_secret, 'seg-portao')
        self.assertNotIn('APP_USR', org.mercadopago_access_token_cifrado)

    @override_settings(DEFAULT_FROM_EMAIL='República RPF <rpf@example.com>')
    def test_remetente_continua_o_do_servidor(self):
        self.assertEqual(Organizacao.objects.get().remetente_email, 'República RPF <rpf@example.com>')


@override_settings(
    MERCADOPAGO_ACCESS_TOKEN='TOKEN-SERVIDOR', MERCADOPAGO_WEBHOOK_SECRET='seg-servidor',
    MERCADOPAGO_NOTIFICATION_URL='https://erp.example.com/financeiro/pix/webhook/',
    DEFAULT_FROM_EMAIL='República RPF <rpf@example.com>',
)
class DoisClientesTests(TestCase):
    def setUp(self):
        self.portao = Organizacao.objects.get()
        self.portao.mercadopago_access_token = 'TOKEN-PORTAO'
        self.portao.mercadopago_webhook_secret = 'seg-portao'
        self.portao.save()
        self.verde = Organizacao.objects.create(
            nome='Casa Verde', nome_curto='CV', slug='casa-verde', segmento='moradia', email_contato='contato@verde.example',
        )

    def test_cliente_sem_token_proprio_nao_usa_o_do_servidor(self):
        with na_organizacao(self.verde):
            self.assertEqual(credenciais_mercado_pago()[1:], ('', ''))
        self.verde.mercadopago_access_token = 'TOKEN-VERDE'
        self.verde.save()
        with na_organizacao(self.verde):
            self.assertEqual(credenciais_mercado_pago()[1], 'TOKEN-VERDE')
        with na_organizacao(self.portao):
            self.assertEqual(credenciais_mercado_pago()[1], 'TOKEN-PORTAO')

    @patch('core.services.pix_gateway.request.urlopen')
    def test_cobranca_vai_para_a_conta_e_o_webhook_do_cliente(self, urlopen):
        self.verde.mercadopago_access_token = 'TOKEN-VERDE'
        self.verde.save()
        resposta = MagicMock()
        resposta.__enter__.return_value.read.return_value = json.dumps(
            {'id': 9, 'status': 'pending', 'point_of_interaction': {'transaction_data': {'qr_code': 'pix'}}}
        ).encode()
        urlopen.return_value = resposta
        with na_organizacao(self.verde):
            criar_cobranca_pix_avulsa(txid='RPFALV1', valor=Decimal('10'), chave_pix='', categoria='Aluguel')
        req = urlopen.call_args.args[0]
        self.assertEqual(req.headers['Authorization'], 'Bearer TOKEN-VERDE')
        self.assertEqual(json.loads(req.data)['notification_url'], 'https://erp.example.com/financeiro/pix/webhook/casa-verde/')

    def test_url_de_notificacao_por_cliente(self):
        self.assertEqual(url_notificacao_mercado_pago(self.portao), 'https://erp.example.com/financeiro/pix/webhook/portao-dos-fundos/')

    @override_settings(DEBUG=False)
    def test_webhook_confere_a_assinatura_com_o_segredo_do_cliente(self):
        self.verde.mercadopago_webhook_secret = 'seg-verde'
        self.verde.save()
        url = reverse('webhook_pix_organizacao', args=['casa-verde'])
        corpo = json.dumps({'txid': 'X', 'status': 'approved'})

        def headers(segredo):
            manifesto = 'request-id:req-1;ts:1700000000;'
            v1 = hmac.new(segredo.encode(), manifesto.encode(), hashlib.sha256).hexdigest()
            return {'HTTP_X_SIGNATURE': f'ts=1700000000,v1={v1}', 'HTTP_X_REQUEST_ID': 'req-1'}

        aceito = self.client.post(url, data=corpo, content_type='application/json', **headers('seg-verde'))
        self.assertEqual(aceito.status_code, 200)
        recusado = self.client.post(url, data=corpo, content_type='application/json', **headers('seg-portao'))
        self.assertEqual(recusado.status_code, 400)

    def test_recibo_sai_com_o_nome_e_o_contato_do_cliente(self):
        with na_organizacao(self.verde):
            morador = Morador.objects.create(nome='Bia', email='bia@example.com')
            cobranca = CobrancaAluguel.objects.create(
                morador=morador, mes_referencia=date(2026, 5, 1), valor=Decimal('5'), txid='RPFALV2', status='pago',
            )
            enviar_comprovante_aluguel_por_email(cobranca)
        self.assertEqual(mail.outbox[0].from_email, 'Casa Verde <rpf@example.com>')
        self.assertEqual(mail.outbox[0].reply_to, ['contato@verde.example'])
        self.assertTrue(mail.outbox[0].body.rstrip().endswith('Casa Verde'))

    def test_rotina_consulta_cada_cliente_com_o_proprio_token(self):
        self.verde.mercadopago_access_token = 'TOKEN-VERDE'
        self.verde.save()
        for org, txid in ((self.portao, 'RPFALP'), (self.verde, 'RPFALV')):
            with na_organizacao(org):
                morador = Morador.objects.create(nome=f'M {txid}')
                CobrancaAluguel.objects.create(
                    morador=morador, mes_referencia=date(2026, 5, 1), valor=Decimal('5'), txid=txid,
                    status='aguardando_pagamento',
                )
        usados = {}

        def consultar(txid):
            usados[txid] = credenciais_mercado_pago()[1]
            return {'status': 'pending'}

        with patch('core.services.aluguel.consultar_status_por_txid', side_effect=consultar):
            verificar_pagamentos_pendentes()
        self.assertEqual(usados, {'RPFALP': 'TOKEN-PORTAO', 'RPFALV': 'TOKEN-VERDE'})

    def test_lembrete_mensal_por_cliente_e_so_com_financeiro(self):
        Organizacao.objects.filter(pk=self.verde.pk).update(segmento='bar', modulos=['moradores', 'compras'])
        with na_organizacao(self.portao):
            Morador.objects.create(nome='Ana', ativo=True)
        with na_organizacao(Organizacao.objects.get(pk=self.verde.pk)):
            Morador.objects.create(nome='Caio', ativo=True)
        call_command('notificar_pagamento_aluguel', '--force', stdout=StringIO())
        self.assertEqual(list(NotificacaoMorador.objects.values_list('morador__nome', flat=True)), ['Ana'])


class AdminDeCredenciaisTests(TestCase):
    def _dados(self, org, **extra):
        dados = {
            'nome': org.nome, 'nome_curto': org.nome_curto, 'slug': org.slug, 'segmento': org.segmento,
            'tema': org.tema, 'termos': '{}', 'ativa': 'on',
        }
        dados.update(extra)
        return dados

    def test_grava_cifrado_mantem_em_branco_e_apaga(self):
        org = Organizacao.objects.get()
        form = OrganizacaoAdminForm(self._dados(org, novo_mercadopago_access_token='APP_USR-novo-token-1234'), instance=org)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        org.refresh_from_db()
        self.assertEqual(org.mercadopago_access_token, 'APP_USR-novo-token-1234')
        self.assertNotIn('APP_USR', org.mercadopago_access_token_cifrado)

        form = OrganizacaoAdminForm(self._dados(org), instance=org)  # em branco: mantém
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        org.refresh_from_db()
        self.assertEqual(org.mercadopago_access_token, 'APP_USR-novo-token-1234')
        self.assertIn('APP_USR-…1234', form.fields['novo_mercadopago_access_token'].help_text)

        form = OrganizacaoAdminForm(self._dados(org, apagar_credenciais_mercadopago='on'), instance=org)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        org.refresh_from_db()
        self.assertEqual(org.mercadopago_access_token, '')

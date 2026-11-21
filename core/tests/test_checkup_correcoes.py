"""Testes de regressão das correções do checkup técnico (nov/2026)."""
import json
from datetime import date, time
from decimal import Decimal

from django.contrib.auth.models import Group, User
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import (
    AtaParticipante,
    AtaReuniao,
    AtaTopico,
    CobrancaAluguel,
    IngressoRock,
    Morador,
    Reuniao,
    RockEvento,
)
from core.services.pdf import gerar_pdf_texto
from core.services.pix_gateway import validar_assinatura_webhook


class PermissaoPorGrupoTests(TestCase):
    def test_membro_do_grupo_ve_controles_de_edicao(self):
        user = User.objects.create_user(username='fin', password='x')
        user.groups.add(Group.objects.create(name='Financeiro'))
        self.client.force_login(user)
        response = self.client.get(reverse('financeiro_aluguel') + '?mes=2026-05')
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'Visualizacao apenas')

    def test_usuario_sem_grupo_nem_acesso_continua_bloqueado(self):
        user = User.objects.create_user(username='nada', password='x')
        self.client.force_login(user)
        response = self.client.get(reverse('financeiro_aluguel'))
        self.assertEqual(response.status_code, 403)


class FinanceiroMesInvalidoTests(TestCase):
    def test_post_com_mes_invalido_nao_gera_erro_500(self):
        user = User.objects.create_superuser(username='admin', password='x', email='a@a.com')
        self.client.force_login(user)
        response = self.client.post(
            reverse('financeiro_aluguel'),
            {'pendencia_submit': '1', 'mes_referencia': 'invalido',
             'pendencia-TOTAL_FORMS': '0', 'pendencia-INITIAL_FORMS': '0'},
        )
        self.assertIn(response.status_code, (200, 302))


class WebhookSemSegredoTests(TestCase):
    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='', DEBUG=False)
    def test_sem_segredo_em_producao_recusa_assinatura(self):
        self.assertFalse(validar_assinatura_webhook(b'{}', ''))

    @override_settings(MERCADOPAGO_WEBHOOK_SECRET='')
    def test_sem_segredo_nao_permite_marcar_aluguel_como_pago(self):
        morador = Morador.objects.create(nome='M', ativo=True)
        cobranca = CobrancaAluguel.objects.create(
            morador=morador, mes_referencia=date(2026, 5, 1), valor=Decimal('10.00'), txid='RPFALFALSO',
        )
        response = self.client.post(
            reverse('webhook_pix'),
            data=json.dumps({'txid': cobranca.txid, 'status': 'pago'}),
            content_type='application/json',
        )
        self.assertEqual(response.status_code, 400)
        cobranca.refresh_from_db()
        self.assertNotEqual(cobranca.status, 'pago')


class GeradorPdfTests(TestCase):
    def test_pdf_quebra_em_varias_paginas_sem_perder_linhas(self):
        linhas = [f'Linha {i}' for i in range(1, 201)]
        pdf = gerar_pdf_texto('Teste', linhas)
        self.assertTrue(pdf.startswith(b'%PDF-1.4'))
        import re
        paginas = int(re.search(rb'/Count (\d+)', pdf).group(1))
        self.assertGreater(paginas, 1)  # 200 linhas não cabem em uma página
        self.assertIn(f'Página {paginas}/{paginas}'.encode('cp1252'), pdf)
        self.assertIn(b'(Linha 200)', pdf)

    def test_pdf_de_ingressos_do_rock_lista_todos(self):
        user = User.objects.create_superuser(username='admin', password='x', email='a@a.com')
        self.client.force_login(user)
        evento = RockEvento.objects.create(nome='Rock', tipo='nosso', quantidade_pessoas=0, data='2026-04-08', valor_arrecadado=0)
        IngressoRock.objects.bulk_create([
            IngressoRock(rock_evento=evento, nome=f'Pessoa {i:03d}') for i in range(80)
        ])
        response = self.client.get(reverse('exportar_ingressos_rock_pdf', args=[evento.id]))
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Pessoa 079', response.content)


class AtaRegistradaTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser(username='sec', password='x', email='s@s.com')
        self.client.force_login(self.user)
        self.reuniao = Reuniao.objects.create(
            tipo='geral', data=date(2026, 4, 10), horario_marcado=time(20, 0), local='Sala', status='realizada',
        )
        self.ata = AtaReuniao.objects.create(
            reuniao=self.reuniao, horario_inicio_real=time(20, 5), horario_fim_real=time(21, 0), criado_por=self.user,
        )
        AtaParticipante.objects.create(ata=self.ata, nome='Alice', presente=True)
        AtaTopico.objects.create(ata=self.ata, ordem=1, texto='Revisão de pendências')

    def test_pdf_da_ata_e_um_pdf_de_verdade(self):
        self.ata.registrar(registrado_por=self.user)
        with self.ata.pdf_final.open('rb') as arquivo:
            conteudo = arquivo.read()
        self.assertTrue(conteudo.startswith(b'%PDF-1.4'))
        self.assertIn('Revisão de pendências'.encode('cp1252'), conteudo)
        self.assertIn(b'Status: Registrada', conteudo)

    def test_post_em_ata_registrada_nao_gera_erro_500(self):
        self.ata.registrar(registrado_por=self.user)
        response = self.client.post(reverse('editar_ata_reuniao', args=[self.reuniao.id]), {'acao': 'salvar'})
        self.assertEqual(response.status_code, 302)

    def test_download_com_arquivo_ausente_redireciona(self):
        self.ata.registrar(registrado_por=self.user)
        self.ata.pdf_final.storage.delete(self.ata.pdf_final.name)
        response = self.client.get(reverse('baixar_ata_pdf', args=[self.reuniao.id]))
        self.assertEqual(response.status_code, 302)


class InfraTests(TestCase):
    def test_logout_encerra_sessao(self):
        user = User.objects.create_user(username='u', password='x')
        self.client.force_login(user)
        response = self.client.post(reverse('logout'))
        self.assertRedirects(response, reverse('login'), fetch_redirect_response=False)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_favicon_aponta_para_arquivo_estatico(self):
        response = self.client.get('/favicon.ico')
        self.assertEqual(response.status_code, 301)
        self.assertIn('core/brand/favicon.svg', response['Location'])

    def test_banco_novo_nao_recebe_moradores_reais(self):
        # A migração 0021 só deve popular o banco da casa, não bancos novos.
        self.assertFalse(Morador.objects.filter(apelido='Panda').exists())

    def test_healthcheck(self):
        response = self.client.get('/healthz')
        self.assertEqual(response.status_code, 200)

"""Módulos ligados por organização (core/modulos.py)."""
import json
from datetime import date

from django.contrib.auth.models import User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.admin import OrganizacaoAdminForm
from core.models import Organizacao, RockEvento
from core.modulos import OBRIGATORIOS, TODOS, modulo_do_caminho, resolver_ativos


class RegistroDeModulosTests(SimpleTestCase):
    def test_vazio_usa_o_pacote_do_segmento(self):
        self.assertEqual(resolver_ativos('moradia', []), frozenset(TODOS))
        mercado = resolver_ativos('mercado', [])
        self.assertNotIn('rock', mercado)
        self.assertNotIn('reunioes', mercado)
        self.assertIn('compras', mercado)

    def test_pessoas_sempre_ligado_e_chaves_desconhecidas_ignoradas(self):
        ativos = resolver_ativos('moradia', ['financeiro', 'modulo-que-nao-existe'])
        self.assertEqual(ativos, frozenset({'financeiro'}) | OBRIGATORIOS)
        self.assertIn('moradores', ativos)

    def test_modulo_pelo_endereco(self):
        self.assertEqual(modulo_do_caminho('/rock/3/lotes/'), 'rock')
        self.assertEqual(modulo_do_caminho('/compras/qrcode/receber/'), 'compras')
        self.assertEqual(modulo_do_caminho('/os/lista/'), 'manutencao')
        self.assertIsNone(modulo_do_caminho('/perfil/'))
        self.assertIsNone(modulo_do_caminho('/rockfest/'))


class ModulosDesligadosTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('dono', 'dono@example.com', 'senha-teste-123')
        self.client.force_login(self.user)

    def _ligar_apenas(self, *modulos):
        Organizacao.objects.update(modulos=list(modulos))

    def test_portao_tem_todos_os_modulos(self):
        self.assertEqual(Organizacao.atual().modulos_ativos, frozenset(TODOS))
        response = self.client.get(reverse('home'))
        for rotulo in ('Financeiro', 'Compras', 'Almoxarifado', 'Rocks', 'Reuniões', 'Calendário'):
            self.assertContains(response, f'>{rotulo}</a>', html=False)

    def test_modulo_desligado_some_do_menu_e_da_pagina_inicial(self):
        self._ligar_apenas('moradores', 'financeiro', 'compras')
        response = self.client.get(reverse('home'))
        self.assertContains(response, '>Financeiro</a>', html=False)
        self.assertNotContains(response, '>Rocks</a>', html=False)
        self.assertNotContains(response, 'Almoxarifado')
        self.assertNotContains(response, 'Próximo rock')
        self.assertNotContains(response, 'reunião marcada')
        self.assertNotContains(response, 'Ver calendário')
        self.assertContains(response, 'Tudo da casa num lugar só: contas e compras.')

    def test_pagina_de_modulo_desligado_responde_404(self):
        self._ligar_apenas('moradores', 'financeiro')
        self.assertEqual(self.client.get(reverse('rock')).status_code, 404)
        self.assertEqual(self.client.get(reverse('compras')).status_code, 404)
        self.assertEqual(self.client.get(reverse('compras_qrcode')).status_code, 404)
        self.assertEqual(self.client.get(reverse('financeiro')).status_code, 200)
        self.assertEqual(self.client.get(reverse('perfil')).status_code, 200)

    def test_webhook_do_pix_continua_aberto(self):
        self._ligar_apenas('moradores')
        response = self.client.post(reverse('webhook_pix'), data='{payload quebrado', content_type='application/json')
        self.assertEqual(response.status_code, 400)  # chegou na view (não 404)
        response = self.client.post(reverse('webhook_pix_financeiro'), data='{payload quebrado', content_type='application/json')
        self.assertEqual(response.status_code, 400)

    def test_calendario_nao_mostra_itens_de_modulo_desligado(self):
        RockEvento.objects.create(nome='Festa Teste', tipo='nosso', data=date(2026, 5, 9))
        response = self.client.get(reverse('calendario') + '?mes=2026-05')
        self.assertContains(response, 'Festa Teste')
        self._ligar_apenas('moradores', 'calendario')
        response = self.client.get(reverse('calendario') + '?mes=2026-05')
        self.assertNotContains(response, 'Festa Teste')

    def test_app_instalavel_sem_compras_nao_oferece_compartilhar_nota(self):
        manifest = json.loads(self.client.get(reverse('pwa_manifest')).content)
        self.assertIn('share_target', manifest)
        self._ligar_apenas('moradores', 'financeiro')
        manifest = json.loads(self.client.get(reverse('pwa_manifest')).content)
        self.assertNotIn('share_target', manifest)


class AdminDeModulosTests(TestCase):
    def _dados(self, org, **extra):
        dados = {
            'nome': org.nome, 'nome_curto': org.nome_curto, 'razao_social': org.razao_social,
            'documento': org.documento, 'cidade': org.cidade, 'nome_recebedor_pix': org.nome_recebedor_pix,
            'slug': org.slug, 'segmento': org.segmento, 'tema': org.tema, 'termos': '{}', 'ativa': 'on',
        }
        dados.update(extra)
        return dados

    def test_caixas_vem_marcadas_com_os_modulos_ligados(self):
        org = Organizacao.atual()
        form = OrganizacaoAdminForm(instance=org)
        self.assertEqual(set(form.initial['modulos']), set(TODOS))

    def test_salvar_inclui_os_obrigatorios_na_ordem_do_registro(self):
        org = Organizacao.atual()
        form = OrganizacaoAdminForm(self._dados(org, modulos=['compras', 'financeiro']), instance=org)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        org.refresh_from_db()
        self.assertEqual(org.modulos, ['moradores', 'financeiro', 'compras'])

    def test_nada_marcado_volta_ao_pacote_do_segmento(self):
        org = Organizacao.atual()
        form = OrganizacaoAdminForm(self._dados(org, segmento='mercado'), instance=org)
        self.assertTrue(form.is_valid(), form.errors)
        form.save()
        org.refresh_from_db()
        self.assertEqual(org.modulos, [])
        self.assertNotIn('rock', org.modulos_ativos)

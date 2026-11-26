"""A marca do cliente vem da Organizacao, não do código.

A República Portão dos Fundos é a organização nº 1 criada pela migração 0070;
trocar os dados dela tem que trocar títulos, PDFs, PIX, email e o app instalado.
"""
import json
import re
from datetime import date
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from django.core import mail
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import CobrancaAluguel, Morador, Organizacao
from core.services.pix_gateway import criar_cobranca_pix_avulsa
from core.views.financeiro import _gerar_pdf_comprovante_aluguel, enviar_comprovante_aluguel_por_email


class PrimeiroClienteTests(TestCase):
    def test_migracao_cria_a_portao_como_organizacao_1(self):
        org = Organizacao.atual()
        self.assertEqual(org.nome, 'República Portão dos Fundos')
        self.assertEqual(org.nome_curto, 'RPF')
        self.assertEqual(org.beneficiario, 'Associação Cultural República Portão dos Fundos')
        self.assertEqual((org.segmento, org.tema), ('moradia', 'portao'))
        # Mesmo nome e cidade que antes estavam fixos no PIX local.
        self.assertEqual(org.dados_pix, ('ASSOC CULT RPF', 'SAO PAULO'))

    def test_sem_organizacao_cadastrada_usa_nome_neutro(self):
        Organizacao.objects.all().delete()
        org = Organizacao.atual()
        self.assertIsNone(org.pk)
        self.assertEqual(org.nome_curto, 'ERP')

    def test_nome_partes_para_a_assinatura_visual(self):
        self.assertEqual(Organizacao(nome='República Portão dos Fundos').nome_partes, ('República', 'Portão dos Fundos'))
        self.assertEqual(Organizacao(nome='Mercadinho').nome_partes, ('', 'Mercadinho'))

    def test_dados_pix_sem_acento_e_no_tamanho_do_padrao(self):
        org = Organizacao(nome='Bar do Zé', razao_social='Bar e Restaurante do Zé Ltda', cidade='São José dos Campos')
        self.assertEqual(org.dados_pix, ('BAR E RESTAURANTE DO ZE L', 'SAO JOSE DOS CA'))


class MarcaDoClienteNasTelasTests(TestCase):
    def setUp(self):
        Organizacao.objects.update(
            nome='Casa Verde', nome_curto='CV', razao_social='Associação Casa Verde',
            nome_recebedor_pix='', cidade='Campinas',
        )
        self.user = User.objects.create_superuser('dono', 'dono@example.com', 'senha-teste-123')

    def test_login_mostra_o_nome_do_cliente(self):
        response = self.client.get(reverse('login'))
        self.assertContains(response, '<title>Entrar | Casa Verde</title>', html=False)
        self.assertNotContains(response, 'Portão')

    def test_paginas_internas_usam_nome_e_sigla_do_cliente(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse('home'))
        self.assertContains(response, '| Casa Verde</title>', html=False)
        self.assertContains(response, '<span class="rpf-marca__republica">Casa</span> Verde', html=False)
        self.assertNotContains(response, 'Portão dos Fundos')

    def test_app_instalavel_usa_o_nome_do_cliente(self):
        manifest = json.loads(self.client.get(reverse('pwa_manifest')).content)
        self.assertEqual(manifest['short_name'], 'CV')
        self.assertEqual(manifest['name'], f'Casa Verde - {settings.PRODUTO_NOME}')

    def test_pix_local_usa_recebedor_e_cidade_do_cliente(self):
        resultado = criar_cobranca_pix_avulsa(txid='RPFAL1', valor=Decimal('10.00'), chave_pix='11999999999')
        self.assertIn('ASSOCIACAO CASA VERDE', resultado['payload_pix'])
        self.assertIn('CAMPINAS', resultado['payload_pix'])

    def test_recibo_pdf_e_email_usam_o_beneficiario_do_cliente(self):
        morador = Morador.objects.create(nome='Ana', email='ana@example.com', ativo=True)
        cobranca = CobrancaAluguel.objects.create(
            morador=morador, mes_referencia=date(2026, 5, 1), valor=Decimal('100.00'), txid='RPFAL9', status='pago',
        )
        pdf = _gerar_pdf_comprovante_aluguel(cobranca)
        self.assertIn('Associação Casa Verde'.encode('cp1252'), pdf)
        self.assertNotIn('Portão'.encode('cp1252'), pdf)

        enviar_comprovante_aluguel_por_email(cobranca)
        self.assertTrue(mail.outbox[0].body.rstrip().endswith('Casa Verde'))


class SemMarcaFixaNoCodigoTests(SimpleTestCase):
    """Trava: o nome do primeiro cliente não pode voltar a ser escrito no código.

    Ficam de fora os desenhos da marca da Portão (SVG/CSS do tema 'portao'),
    as migrações (histórico) e os testes.
    """
    PADRAO = re.compile(r'Port[aã]o dos Fundos|ASSOC CULT RPF|Associação Cultural República')

    def test_templates_views_e_servicos_nao_citam_a_portao(self):
        core = Path(settings.BASE_DIR) / 'core'
        pastas = [core / 'templates', core / 'views', core / 'services']
        achados = []
        for pasta in pastas:
            for arquivo in pasta.rglob('*'):
                if arquivo.suffix in {'.py', '.html', '.js'} and self.PADRAO.search(arquivo.read_text(encoding='utf-8')):
                    achados.append(str(arquivo.relative_to(core)))
        self.assertEqual(achados, [], 'Use {{ organizacao.* }} / Organizacao.atual() no lugar do nome fixo.')

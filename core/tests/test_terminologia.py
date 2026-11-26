"""Vocabulário por segmento e por organização (core/terminologia.py)."""
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Organizacao
from core.terminologia import PRESETS, Termos, validar_termos


class TermosTests(SimpleTestCase):
    def test_republica_mantem_os_termos_de_sempre(self):
        t = Termos('moradia')
        self.assertEqual(
            [t['Membros'], t['cobranca'], t['Eventos'], t['do_local'], t['no_local'], t['unidade']],
            ['Moradores', 'aluguel', 'Rocks', 'da casa', 'na casa', 'quarto'],
        )

    def test_artigos_seguem_genero_e_numero(self):
        t = Termos('agro')
        self.assertEqual(t['do_local'], 'da propriedade')
        self.assertEqual(t['os_membros'], 'os colaboradores')
        self.assertEqual(t['Os_eventos'], 'Os eventos')
        self.assertEqual(t['um_membro'], 'um colaborador')
        self.assertEqual(t['Unidades'], 'Talhões')
        self.assertEqual(Termos('bar')['do_local'], 'do bar')

    def test_format_map_para_textos_no_python(self):
        self.assertEqual('{Membros} {do_local}'.format_map(Termos('mercado')), 'Colaboradores da loja')

    def test_ajuste_da_organizacao_sobrepoe_o_segmento(self):
        t = Termos('moradia', {'evento': ['festa', 'festas', 'f']})
        self.assertEqual((t['Eventos'], t['o_evento'], t['membro']), ('Festas', 'a festa', 'morador'))

    def test_segmento_desconhecido_usa_termos_genericos(self):
        self.assertEqual(Termos('nao-existe')['membros'], 'membros')

    def test_chave_inexistente_da_erro(self):
        with self.assertRaises(KeyError):
            Termos('moradia')['cliente']
        with self.assertRaises(KeyError):
            Termos('moradia')['xyz_membro']

    def test_todos_os_segmentos_tem_todas_as_chaves(self):
        for segmento, termos in PRESETS.items():
            self.assertEqual(set(termos), {'membro', 'local', 'cobranca', 'evento', 'unidade'}, segmento)

    def test_validacao_dos_ajustes(self):
        self.assertEqual(validar_termos({'membro': ['sócio', 'sócios', 'm']}), [])
        self.assertTrue(validar_termos({'cliente': ['a', 'b', 'm']}))
        self.assertTrue(validar_termos({'membro': ['sócio', 'sócios']}))
        self.assertTrue(validar_termos({'membro': ['sócio', 'sócios', 'x']}))
        self.assertTrue(validar_termos(['membro']))
        # Ajuste inválido é ignorado em vez de quebrar as telas.
        self.assertEqual(Termos('moradia', {'membro': 'sócio'})['membro'], 'morador')

    def test_organizacao_valida_os_ajustes_no_admin(self):
        org = Organizacao(nome='X', nome_curto='X', slug='x', termos={'membro': ['a']})
        with self.assertRaises(ValidationError):
            org.clean()


class VocabularioNasTelasTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_superuser('dono', 'dono@example.com', 'senha-teste-123')
        self.client.force_login(self.user)

    def test_portao_continua_falando_de_moradores_e_rocks(self):
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Painel da casa')
        self.assertContains(response, '>Moradores</a>', html=False)
        self.assertContains(response, '>Rocks</a>', html=False)
        self.assertContains(response, 'Tudo da casa num lugar só: contas, compras, rocks e reuniões.')

    def test_bar_ve_colaboradores_e_eventos(self):
        Organizacao.objects.update(nome='Bar do Zé', nome_curto='BZ', segmento='bar')
        response = self.client.get(reverse('home'))
        self.assertContains(response, 'Painel do bar')
        self.assertContains(response, '>Colaboradores</a>', html=False)
        self.assertContains(response, '>Eventos</a>', html=False)
        self.assertContains(response, 'Áreas do bar')
        self.assertNotContains(response, 'Moradores')
        self.assertNotContains(response, 'Rocks')

        response = self.client.get(reverse('moradores'))
        self.assertContains(response, '<title>Colaboradores | Bar do Zé</title>', html=False)
        self.assertContains(response, 'em qual setor')

    def test_ajuste_fino_aparece_no_menu(self):
        Organizacao.objects.update(termos={'membro': ['sócio', 'sócios', 'm']})
        response = self.client.get(reverse('home'))
        self.assertContains(response, '>Sócios</a>', html=False)
        self.assertContains(response, '>Rocks</a>', html=False)

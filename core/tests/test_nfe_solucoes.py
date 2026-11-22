"""Testes das quatro formas de trazer a nota sem passar pelo robô da SEFAZ:
foto (Claude), atalho/compartilhar, XML (upload e e-mail) e Receita (A1)."""
import base64
import gzip
import io
import json
from datetime import date, datetime, timedelta, timezone as dt_timezone
from decimal import Decimal
from email.message import EmailMessage
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives.serialization import BestAvailableEncryption, pkcs12
from cryptography.x509.oid import NameOID
from django.contrib.auth.models import Group, User
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from core.models import ControleDistribuicaoNFe, NotaFiscal
from core.services.nfce import digito_verificador_chave
from core.services.nfce_foto import FotoNotaInvalida, ItemFoto, NotaFoto, extrair_nota_da_foto, nota_foto_para_dados
from core.services.nfe_distribuicao import ConfigDistribuicao, importar_distribuicao, ler_resposta, montar_envelope
from core.services.nfe_importacao import ConfigEmailNotas, importar_notas_do_email
from core.services.nfe_xml import XMLNotaInvalido, ler_xml_nota, resumo_autorizado_de_compra

from .test_nfce import CHAVE_MG, HTML_MG_CAPTCHA, TEXTO_MG_COPIADO, URL_MG

# NF-e (55) de MG para o CNPJ da república
CHAVE_NFE_43 = '31' + '2611' + '11222333000181' + '55' + '001' + '000004567' + '1' + '23456789'
CHAVE_NFE = CHAVE_NFE_43 + str(digito_verificador_chave(CHAVE_NFE_43))

XML_PROC = f"""<?xml version="1.0" encoding="UTF-8"?>
<nfeProc xmlns="http://www.portalfiscal.inf.br/nfe" versao="4.00">
  <NFe><infNFe Id="NFe{CHAVE_MG}" versao="4.00">
    <ide><cUF>31</cUF><mod>65</mod><serie>1</serie><nNF>2630192</nNF><dhEmi>2026-11-14T18:22:59-03:00</dhEmi></ide>
    <emit><CNPJ>23960651000129</CNPJ><xNome>MERCADINHO VILELA LTDA</xNome><xFant>MERCADINHO VILELA</xFant></emit>
    <det nItem="1"><prod><cProd>789</cProd><xProd>ARROZ TIPO 1 5KG</xProd><uCom>UN</uCom><qCom>2.0000</qCom><vUnCom>24.9000000000</vUnCom><vProd>49.80</vProd></prod></det>
    <det nItem="2"><prod><cProd>123</cProd><xProd>BANANA PRATA</xProd><uCom>KG</uCom><qCom>1.2350</qCom><vUnCom>6.99</vUnCom><vProd>8.63</vProd><vDesc>0.63</vDesc></prod></det>
    <total><ICMSTot><vProd>58.43</vProd><vDesc>0.63</vDesc><vNF>57.80</vNF></ICMSTot></total>
  </infNFe></NFe>
  <protNFe versao="4.00"><infProt><chNFe>{CHAVE_MG}</chNFe><cStat>100</cStat></infProt></protNFe>
</nfeProc>
"""

XML_RESUMO = f"""<resNFe xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01">
  <chNFe>{CHAVE_NFE}</chNFe><CNPJ>11222333000181</CNPJ><xNome>CASA DO CONSTRUTOR LTDA</xNome><IE>123</IE>
  <dhEmi>2026-11-10T10:00:00-03:00</dhEmi><tpNF>1</tpNF><vNF>350.00</vNF><digVal>abc</digVal>
  <dhRecbto>2026-11-10T10:00:05-03:00</dhRecbto><nProt>131</nProt><cSitNFe>1</cSitNFe>
</resNFe>"""


def _doc_zip(xml: str) -> str:
    return base64.b64encode(gzip.compress(xml.encode('utf-8'))).decode('ascii')


def _soap(status: str, ult: str, maximo: str, docs: list[tuple[str, str, str]] = ()) -> bytes:
    lote = ''.join(f'<docZip NSU="{nsu}" schema="{schema}">{_doc_zip(xml)}</docZip>' for nsu, schema, xml in docs)
    return f"""<?xml version="1.0" encoding="utf-8"?>
<soap:Envelope xmlns:soap="http://www.w3.org/2003/05/soap-envelope"><soap:Body>
<nfeDistDFeInteresseResponse xmlns="http://www.portalfiscal.inf.br/nfe/wsdl/NFeDistribuicaoDFe"><nfeDistDFeInteresseResult>
<retDistDFeInt xmlns="http://www.portalfiscal.inf.br/nfe" versao="1.01"><tpAmb>1</tpAmb><cStat>{status}</cStat>
<xMotivo>motivo {status}</xMotivo><ultNSU>{ult}</ultNSU><maxNSU>{maximo}</maxNSU>
{'<loteDistDFeInt>' + lote + '</loteDistDFeInt>' if lote else ''}</retDistDFeInt>
</nfeDistDFeInteresseResult></nfeDistDFeInteresseResponse></soap:Body></soap:Envelope>""".encode('utf-8')


def _pfx(senha=b'1234') -> bytes:
    chave = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    nome = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'REPUBLICA TESTE:11222333000181')])
    agora = datetime.now(dt_timezone.utc)
    certificado = (
        x509.CertificateBuilder().subject_name(nome).issuer_name(nome).public_key(chave.public_key())
        .serial_number(1).not_valid_before(agora - timedelta(days=1)).not_valid_after(agora + timedelta(days=30))
        .sign(chave, hashes.SHA256())
    )
    return pkcs12.serialize_key_and_certificates(b'teste', chave, certificado, None, BestAvailableEncryption(senha))


def _foto_png() -> bytes:
    saida = io.BytesIO()
    Image.new('RGB', (40, 60), 'white').save(saida, format='PNG')
    return saida.getvalue()


def _nota_foto(**extra) -> NotaFoto:
    dados = {
        'eh_nota_fiscal': True,
        'loja': 'MERCADINHO VILELA',
        'cnpj': '23.960.651/0001-29',
        'data_emissao': '2026-11-14',
        'chave_acesso': ' '.join(CHAVE_MG[i:i + 4] for i in range(0, 44, 4)),
        'numero_nota': '2630192',
        'valor_pago': 57.80,
        'itens': [
            ItemFoto(descricao='ARROZ TIPO 1 5KG', quantidade=2, unidade='UN', valor_unitario=24.9, valor_total=49.8),
            ItemFoto(descricao='BANANA PRATA', quantidade=1.235, unidade='KG', valor_unitario=6.99, valor_total=8.0),
        ],
    }
    dados.update(extra)
    return NotaFoto(**dados)


def _cliente_claude(nota: NotaFoto | None, stop_reason='end_turn'):
    cliente = MagicMock()
    cliente.beta.messages.parse.return_value = SimpleNamespace(stop_reason=stop_reason, parsed_output=nota)
    return cliente


class XMLNotaTests(SimpleTestCase):
    def test_le_proc_nfce_com_itens_desconto_e_total(self):
        dados = ler_xml_nota(XML_PROC)
        self.assertEqual(dados.chave_acesso, CHAVE_MG)
        self.assertEqual(dados.fornecedor, 'MERCADINHO VILELA')
        self.assertEqual(dados.cnpj_emitente, '23960651000129')
        self.assertEqual(dados.data_emissao, date(2026, 11, 14))
        self.assertEqual(dados.valor_total, Decimal('57.80'))
        arroz, banana = dados.itens
        self.assertEqual((arroz.quantidade, arroz.valor_unitario, arroz.valor_total), (Decimal('2'), Decimal('24.90'), Decimal('49.80')))
        self.assertEqual((banana.quantidade, banana.valor_total), (Decimal('1.2350'), Decimal('8.00')))

    def test_le_resumo_da_receita(self):
        dados = ler_xml_nota(XML_RESUMO)
        self.assertEqual((dados.chave_acesso, dados.fornecedor, dados.valor_total), (CHAVE_NFE, 'CASA DO CONSTRUTOR LTDA', Decimal('350.00')))
        self.assertEqual(dados.modelo, '55')
        self.assertTrue(resumo_autorizado_de_compra(XML_RESUMO))
        self.assertFalse(resumo_autorizado_de_compra(XML_RESUMO.replace('<cSitNFe>1', '<cSitNFe>3')))

    def test_xml_invalido_ou_perigoso_e_recusado(self):
        for conteudo in ('não é xml', '<html/>', '<!DOCTYPE x [<!ENTITY a "b">]><x>&a;</x>'):
            with self.assertRaises(XMLNotaInvalido):
                ler_xml_nota(conteudo)


class FotoNotaTests(SimpleTestCase):
    def test_converte_leitura_da_foto_com_chave(self):
        cliente = _cliente_claude(_nota_foto())
        nota = extrair_nota_da_foto(_foto_png(), cliente=cliente)
        dados = nota_foto_para_dados(nota)
        self.assertEqual(dados.chave_acesso, CHAVE_MG)
        self.assertEqual(dados.valor_total, Decimal('57.80'))
        self.assertEqual(dados.data_emissao, date(2026, 11, 14))
        self.assertEqual(len(dados.itens), 2)
        chamada = cliente.beta.messages.parse.call_args.kwargs
        self.assertEqual(chamada['model'], 'claude-opus-5-5')
        self.assertEqual(chamada['fallbacks'], 'default')
        self.assertEqual(chamada['output_format'], NotaFoto)
        imagem = chamada['messages'][0]['content'][0]
        self.assertEqual((imagem['type'], imagem['source']['media_type']), ('image', 'image/jpeg'))

    def test_foto_sem_chave_avisa_que_nao_ha_controle_de_duplicidade(self):
        dados = nota_foto_para_dados(_nota_foto(chave_acesso=''))
        self.assertEqual(dados.chave_acesso, '')
        self.assertEqual(dados.cnpj_emitente, '23960651000129')
        self.assertIn('sem a chave de acesso', dados.aviso_consulta)

    def test_recusa_foto_que_nao_e_nota_ou_recusada(self):
        with self.assertRaises(FotoNotaInvalida):
            nota_foto_para_dados(_nota_foto(eh_nota_fiscal=False))
        with self.assertRaises(FotoNotaInvalida):
            extrair_nota_da_foto(_foto_png(), cliente=_cliente_claude(None, stop_reason='refusal'))
        with self.assertRaises(FotoNotaInvalida):
            extrair_nota_da_foto(b'nao e imagem', cliente=_cliente_claude(_nota_foto()))


class DistribuicaoTests(TestCase):
    def setUp(self):
        self.config = ConfigDistribuicao(cnpj='11222333000181', pfx=_pfx(), senha='1234', uf_autor='31')

    def test_envelope_tem_cnpj_uf_e_nsu(self):
        envelope = montar_envelope(self.config, '12')
        for trecho in ('<CNPJ>11222333000181</CNPJ>', '<cUFAutor>31</cUFAutor>', '<ultNSU>000000000000012</ultNSU>', 'versao="1.01"'):
            self.assertIn(trecho, envelope)

    def test_le_resposta_com_documentos(self):
        resposta = ler_resposta(_soap('138', '5', '5', [('5', 'resNFe_v1.01.xsd', XML_RESUMO)]))
        self.assertEqual((resposta.status, resposta.ult_nsu, resposta.max_nsu), ('138', '5', '5'))
        self.assertEqual(resposta.documentos[0][1], 'resNFe_v1.01.xsd')
        self.assertIn(b'CASA DO CONSTRUTOR', resposta.documentos[0][2])

    def test_importa_resumo_e_nota_completa_e_respeita_espera(self):
        respostas = [
            _soap('138', '2', '3', [('1', 'resNFe_v1.01.xsd', XML_RESUMO), ('2', 'resEvento_v1.01.xsd', '<x/>')]),
            _soap('138', '3', '3', [('3', 'procNFe_v4.00.xsd', XML_PROC)]),
        ]
        chamadas = []

        def post(url, data, headers, cert, timeout):
            chamadas.append({'url': url, 'cert': cert, 'data': data})
            return SimpleNamespace(status_code=200, content=respostas.pop(0))

        resultado = importar_distribuicao(self.config, post=post)
        self.assertEqual((resultado.registradas, resultado.repetidas), (2, 0))
        self.assertEqual(len(chamadas), 2)
        self.assertEqual(len(chamadas[0]['cert']), 2)
        construtor = NotaFiscal.objects.get(chave_acesso=CHAVE_NFE)
        self.assertEqual((construtor.valor, construtor.fornecedor, construtor.status), (Decimal('350.00'), 'CASA DO CONSTRUTOR LTDA', 'pendente'))
        self.assertIn('Receita (certificado A1)', construtor.observacao)
        self.assertTrue(NotaFiscal.objects.filter(chave_acesso=CHAVE_MG, valor=Decimal('57.80')).exists())
        controle = ControleDistribuicaoNFe.objects.get()
        self.assertEqual(controle.ult_nsu, '000000000000003')

        # Sem novidade: a Receita manda esperar 1 hora, e a próxima rodada nem consulta.
        respostas.append(_soap('137', '3', '3'))
        importar_distribuicao(self.config, post=post)
        controle.refresh_from_db()
        self.assertGreater(controle.proxima_consulta_apos, timezone.now() + timedelta(minutes=50))
        antes = len(chamadas)
        resultado = importar_distribuicao(self.config, post=post)
        self.assertEqual(len(chamadas), antes)
        self.assertIn('Aguardando', resultado.erros[0])
        self.assertEqual(NotaFiscal.objects.count(), 2)


class EmailNotasTests(TestCase):
    def _mensagem(self):
        msg = EmailMessage()
        msg['Subject'] = 'Sua NFC-e'
        msg.set_content('Segue a nota.')
        msg.add_attachment(XML_PROC.encode('utf-8'), maintype='application', subtype='xml', filename='nfce.xml')
        return msg.as_bytes()

    def _imap(self, mensagens):
        marcadas = []

        class FakeIMAP:
            def __init__(self, host, porta):
                self.host = host

            def login(self, usuario, senha):
                return 'OK', []

            def select(self, pasta):
                return 'OK', []

            def search(self, charset, criterio):
                return 'OK', [b' '.join(str(i + 1).encode() for i in range(len(mensagens)))]

            def fetch(self, numero, partes):
                return 'OK', [(b'1 (RFC822)', mensagens[int(numero) - 1])]

            def store(self, numero, acao, flag):
                marcadas.append(numero)

            def logout(self):
                pass

        return FakeIMAP, marcadas

    def test_importa_xml_anexado_sem_duplicar(self):
        config = ConfigEmailNotas(host='imap.exemplo.com', usuario='notas@exemplo.com', senha='x')
        imap, marcadas = self._imap([self._mensagem(), self._mensagem()])
        resultado = importar_notas_do_email(config, imap_cls=imap)
        self.assertEqual((resultado.lidas, resultado.registradas, resultado.repetidas), (2, 1, 1))
        self.assertEqual(marcadas, [b'1', b'2'])
        nota = NotaFiscal.objects.get()
        self.assertEqual((nota.valor, nota.fornecedor, nota.chave_acesso), (Decimal('57.80'), 'MERCADINHO VILELA', CHAVE_MG))
        self.assertIn('e-mail', nota.observacao)


@patch('core.services.nfce.buscar_nome_empresa', return_value='')
@patch('core.views.compras_nfce.buscar_nome_empresa', return_value='')
class TelaSolucoesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='compras_sol', password='123456')
        self.user.groups.add(Group.objects.get_or_create(name='Compras')[0])
        self.client.force_login(self.user)

    def test_pagina_inicial_mostra_as_quatro_opcoes(self, *_):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'x'}):
            response = self.client.get(reverse('compras_qrcode'))
        for texto in ('Fotografar a nota inteira', 'Enviar ao RPF', 'Ler XML', 'Importação automática'):
            self.assertContains(response, texto)
        self.assertContains(response, reverse('compras_nfce_receber'))

    def test_foto_desligada_sem_chave(self, *_):
        with patch.dict('os.environ', {'ANTHROPIC_API_KEY': ''}):
            response = self.client.get(reverse('compras_qrcode'))
        self.assertContains(response, 'ANTHROPIC_API_KEY')
        self.assertNotContains(response, 'Fotografar a nota inteira')

    def test_foto_vira_tela_de_conferencia_e_registra(self, *_):
        with patch('core.services.nfce_foto._cliente', return_value=_cliente_claude(_nota_foto())), \
                patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'x'}):
            response = self.client.post(reverse('compras_qrcode'), {
                'acao': 'foto', 'foto_nota': SimpleUploadedFile('nota.png', _foto_png(), 'image/png'),
            })
        self.assertContains(response, 'Nota lida pela foto: 2 item(ns)')
        self.assertContains(response, 'value="57.80"')
        self.assertContains(response, 'value="MERCADINHO VILELA"')
        self.client.post(reverse('compras_qrcode'), {
            'acao': 'confirmar', 'fornecedor': 'MERCADINHO VILELA', 'descricao': 'Compra com 2 itens',
            'data_emissao': '2026-11-14', 'valor_total': '57.80', 'modo': 'total', 'categoria_compra': 'geral',
            'tipo_item': 'Bem de Consumo', 'cobrar_no_aluguel': 'on', 'status': 'pendente', 'forma_pagamento': '',
        })
        nota = NotaFiscal.objects.get()
        self.assertEqual((nota.chave_acesso, nota.valor), (CHAVE_MG, Decimal('57.80')))
        self.assertIn('foto da nota', nota.observacao)

    def test_foto_completa_leitura_de_mg_bloqueada(self, *_):
        with patch('core.services.nfce._baixar_pagina', return_value=HTML_MG_CAPTCHA):
            self.client.post(reverse('compras_qrcode'), {'acao': 'ler', 'conteudo_qrcode': URL_MG})
        with patch('core.services.nfce_foto._cliente', return_value=_cliente_claude(_nota_foto(chave_acesso=''))), \
                patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'x'}):
            response = self.client.post(reverse('compras_qrcode'), {
                'acao': 'foto', 'completar': '1', 'foto_nota': SimpleUploadedFile('n.png', _foto_png(), 'image/png'),
            })
        self.assertContains(response, 'ARROZ TIPO 1 5KG')
        sessao = self.client.session['nfce_leitura']
        self.assertEqual(sessao['chave_acesso'], CHAVE_MG)

    def test_foto_de_outra_loja_e_recusada_ao_completar(self, *_):
        with patch('core.services.nfce._baixar_pagina', return_value=HTML_MG_CAPTCHA):
            self.client.post(reverse('compras_qrcode'), {'acao': 'ler', 'conteudo_qrcode': URL_MG})
        with patch('core.services.nfce_foto._cliente', return_value=_cliente_claude(_nota_foto(cnpj='11222333000181'))), \
                patch.dict('os.environ', {'ANTHROPIC_API_KEY': 'x'}):
            response = self.client.post(reverse('compras_qrcode'), {
                'acao': 'foto', 'completar': '1', 'foto_nota': SimpleUploadedFile('n.png', _foto_png(), 'image/png'),
            })
        self.assertContains(response, 'outra loja')
        self.assertContains(response, 'Colar nota copiada')

    def test_upload_de_xml(self, *_):
        response = self.client.post(reverse('compras_qrcode'), {
            'acao': 'xml', 'xml_nota': SimpleUploadedFile('nota.xml', XML_PROC.encode(), 'text/xml'),
        })
        self.assertContains(response, 'XML lido: 2 item(ns).')
        self.assertContains(response, 'value="57.80"')

    def test_receber_sem_login_so_mostra_botao_e_importar_preenche(self, *_):
        self.client.logout()
        response = self.client.post(reverse('compras_nfce_receber'), {'url': URL_MG, 'text': TEXTO_MG_COPIADO})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Importar nota')
        self.assertContains(response, 'name="acao" value="importar"')
        self.assertEqual(NotaFiscal.objects.count(), 0)

        self.client.force_login(self.user)
        response = self.client.post(reverse('compras_qrcode'), {
            'acao': 'importar', 'conteudo_qrcode': URL_MG, 'texto_nota': TEXTO_MG_COPIADO,
        })
        self.assertContains(response, 'Nota lida: 3 item(ns).')
        self.assertContains(response, 'value="1292.99"')
        self.assertEqual(self.client.session['nfce_leitura']['chave_acesso'], CHAVE_MG)

    def test_compartilhar_so_com_link_e_get_vazio(self, *_):
        response = self.client.post(reverse('compras_nfce_receber'), {'text': URL_MG})
        self.assertContains(response, 'Importar nota')
        self.assertContains(response, 'value="https://portalsped.fazenda.mg.gov.br')
        response = self.client.get(reverse('compras_nfce_receber'))
        self.assertContains(response, 'Nada para importar')

    def test_manifest_e_service_worker(self, *_):
        manifest = json.loads(self.client.get(reverse('pwa_manifest')).content)
        self.assertEqual(manifest['share_target']['action'], reverse('compras_nfce_receber'))
        self.assertEqual(manifest['share_target']['method'], 'POST')
        resposta = self.client.get(reverse('pwa_service_worker'))
        self.assertEqual(resposta['Content-Type'], 'application/javascript')

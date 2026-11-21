import json
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch
from urllib import error

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Morador, NotaFiscal
from core.services.nfce import (
    QRCodeNFCeInvalido,
    TextoNFCeInvalido,
    aplicar_texto_copiado,
    buscar_nome_empresa,
    extrair_dados_texto_copiado,
    chave_acesso_valida,
    consultar_nfce,
    digito_verificador_chave,
    extrair_dados_pagina_sefaz,
    interpretar_qrcode_nfce,
)

# SP (35), abr/2026, CNPJ 12.345.678/0001-95, modelo 65, série 1, nº 12345
CHAVE_43 = '35' + '2604' + '12345678000195' + '65' + '001' + '000012345' + '1' + '87654321'
CHAVE = CHAVE_43 + str(digito_verificador_chave(CHAVE_43))
URL_ONLINE = f'https://www.nfce.fazenda.sp.gov.br/NFCeConsultaPublica/Paginas/ConsultaQRCode.aspx?p={CHAVE}|2|1|1|ABCDEF0123456789'

HTML_SEFAZ = """
<html><body>
<div id="conteudo">
  <div class="txtCenter">
    <div id="u20" class="txtTopo">SUPERMERCADO EXEMPLO LTDA</div>
    <div class="text">CNPJ: 12.345.678/0001-95</div>
  </div>
  <table id="tabResult">
    <tr id="Item + 1">
      <td valign="top">
        <span class="txtTit">ARROZ TIPO 1 5KG</span><span class="RCod">(Código: 789 )</span><br/>
        <span class="Rqtd"><strong>Qtde.:</strong>2</span>
        <span class="RUN"><strong>UN: </strong>UN</span>
        <span class="RvlUnit"><strong>Vl. Unit.:</strong>&nbsp;&nbsp;24,90</span>
      </td>
      <td align="right" valign="top" class="txtTit noWrap">Vl. Total<br/><span class="valor">49,80</span></td>
    </tr>
    <tr id="Item + 2">
      <td valign="top">
        <span class="txtTit">BANANA PRATA</span><span class="RCod">(Código: 123 )</span><br/>
        <span class="Rqtd"><strong>Qtde.:</strong>1,235</span>
        <span class="RUN"><strong>UN: </strong>KG</span>
        <span class="RvlUnit"><strong>Vl. Unit.:</strong>&nbsp;&nbsp;6,99</span>
      </td>
      <td align="right" valign="top" class="txtTit noWrap">Vl. Total<br/><span class="valor">8,63</span></td>
    </tr>
  </table>
  <div id="totalNota" class="txtRight">
    <div id="linhaTotal"><label>Qtd. total de itens:</label><span class="totalNumb">2</span></div>
    <div id="linhaTotal"><label>Valor total R$:</label><span class="totalNumb">58,43</span></div>
    <div id="linhaTotal" class="linhaShade"><label>Valor a pagar R$:</label><span class="totalNumb txtMax">58,43</span></div>
  </div>
  <div id="infos"><ul><li><strong>Número: </strong>12345 <strong>Série: </strong>1 <strong>Emissão: </strong>14/04/2026 18:22:31 - Via Consumidor</li></ul></div>
</div>
</body></html>
"""


# MG (31), nov/2026, CNPJ 23.960.651/0001-29, modelo 65, série 1, nº 2630192
CHAVE_MG_43 = '31' + '2611' + '23960651000129' + '65' + '001' + '002630192' + '1' + '12345678'
CHAVE_MG = CHAVE_MG_43 + str(digito_verificador_chave(CHAVE_MG_43))
URL_MG = f'https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p={CHAVE_MG}|2|1|1|ABCDEF0123456789'

# Resumo do que o portal de MG devolve hoje para um acesso sem navegador.
HTML_MG_CAPTCHA = """
<html><body><form id="formPrincipal">
  <h4>Nota Fiscal de Consumidor Eletrônica - Visualização dados qrcode NFC-e</h4>
  <div class="panel-body"><b>2. </b>reCAPTCHA é um serviço que protege este site contra spam e abuso.</div>
  <div class="g-recaptcha"><script>jQuery.getScript("https://challenges.cloudflare.com/turnstile/v0/api.js")</script>
  <div class="cf-turnstile" data-sitekey="x"></div></div>
  <a href="#" class="btn btn-primary">Visualizar</a>
</form></body></html>
"""


# Texto como sai de "Selecionar tudo > Copiar" na nota de MG depois do "não sou robô"
# (layout de uma impressão real do portal, com dados trocados).
TEXTO_MG_COPIADO = """Nota Fiscal de Consumidor Eletrônica (NFC-e)
MERCADINHO VILELA LTDA
CNPJ: 23960651000129 -, Inscrição Estadual: 0012345670099
RUA DOS ESTUDANTES, 100, CENTRO, 3171303 - VICOSA, MG
Filtar ítens...
ARROZ TIPO 1 5KG (Código:
789)
Qtde total de ítens:
2.0000
UN:
UN
Valor total R$: R$
49,80
BANANA PRATA (Código:
123)
Qtde total de ítens:
1.2350
UN:
KG
Valor total R$: R$
8,63
CERVEJA LATA 350ML (Código: 555)\tQtde total de ítens: 12.0000\tUN: LT\tValor total R$: R$ 1.234,56
Qtde total de ítens 3
Valor total R$ 1293.99
Descontos R$ 1.00
Valor pago R$ 1292.99
Forma de Pagamento 04 - Cartão de Débito
Consumidor
Chave de acesso
Informações gerais da Nota
Emitente
Nome / Razão Social CNPJ Inscrição Estadual UF
Modelo Série Número Data Emissão
65 1 2630192 14/11/2026 18:22:59
Protocolo
131230723140907
"""


class TextoCopiadoTests(SimpleTestCase):
    def test_le_itens_total_loja_e_data_do_texto_de_mg(self):
        extraido = extrair_dados_texto_copiado(TEXTO_MG_COPIADO)
        self.assertEqual(extraido['fornecedor'], 'MERCADINHO VILELA LTDA')
        self.assertEqual(extraido['cnpj'], '23960651000129')
        self.assertEqual(extraido['data_emissao'], date(2026, 11, 14))
        self.assertEqual(extraido['valor_total'], Decimal('1292.99'))
        arroz, banana, cerveja = extraido['itens']
        self.assertEqual((arroz.descricao, arroz.quantidade, arroz.unidade), ('ARROZ TIPO 1 5KG', Decimal('2'), 'UN'))
        self.assertEqual((arroz.valor_unitario, arroz.valor_total), (Decimal('24.90'), Decimal('49.80')))
        self.assertEqual((banana.descricao, banana.quantidade, banana.unidade, banana.valor_total),
                         ('BANANA PRATA', Decimal('1.2350'), 'KG', Decimal('8.63')))
        self.assertEqual((cerveja.descricao, cerveja.quantidade, cerveja.valor_total),
                         ('CERVEJA LATA 350ML', Decimal('12'), Decimal('1234.56')))
        self.assertEqual(str(cerveja.quantidade), '12')

    def test_le_texto_copiado_do_layout_padrao(self):
        texto = 'SUPERMERCADO X\nCNPJ: 12.345.678/0001-95\nARROZ (Código: 789 ) Qtde.:2 UN: UN Vl. Unit.: 24,90 Vl. Total 49,80\nValor a pagar R$: 49,80'
        extraido = extrair_dados_texto_copiado(texto)
        self.assertEqual(extraido['valor_total'], Decimal('49.80'))
        self.assertEqual(extraido['itens'][0].descricao, 'ARROZ')
        self.assertEqual(extraido['fornecedor'], 'SUPERMERCADO X')

    def test_texto_sem_nota_da_erro(self):
        with self.assertRaises(TextoNFCeInvalido):
            extrair_dados_texto_copiado('Não sou um robô\nVisualizar')

    def test_texto_de_outra_loja_e_recusado(self):
        dados = interpretar_qrcode_nfce(URL_ONLINE)  # CNPJ 12.345.678/0001-95
        with self.assertRaisesMessage(TextoNFCeInvalido, 'outra loja'):
            aplicar_texto_copiado(dados, TEXTO_MG_COPIADO)

    def test_aplicar_completa_a_leitura(self):
        dados = interpretar_qrcode_nfce(URL_MG)
        dados.sefaz_pede_verificacao = True
        dados.aviso_consulta = 'x'
        aplicar_texto_copiado(dados, TEXTO_MG_COPIADO)
        self.assertTrue(dados.consulta_sefaz_ok)
        self.assertFalse(dados.sefaz_pede_verificacao)
        self.assertEqual(dados.aviso_consulta, '')
        self.assertEqual(len(dados.itens), 3)
        self.assertEqual(dados.valor_total, Decimal('1292.99'))


class InterpretarQRCodeTests(SimpleTestCase):
    def test_nota_do_mes_corrente_sugere_a_data_de_hoje(self):
        with patch('core.services.nfce.timezone.localdate', return_value=date(2026, 11, 21)):
            self.assertEqual(interpretar_qrcode_nfce(URL_MG).data_emissao, date(2026, 11, 21))
        with patch('core.services.nfce.timezone.localdate', return_value=date(2026, 12, 2)):
            self.assertEqual(interpretar_qrcode_nfce(URL_MG).data_emissao, date(2026, 11, 1))

    def test_chave_com_digito_errado_e_invalida(self):
        self.assertTrue(chave_acesso_valida(CHAVE))
        errada = CHAVE[:43] + str((int(CHAVE[43]) + 1) % 10)
        self.assertFalse(chave_acesso_valida(errada))

    def test_qrcode_online_extrai_dados_da_chave(self):
        dados = interpretar_qrcode_nfce(URL_ONLINE)
        self.assertEqual(dados.chave_acesso, CHAVE)
        self.assertEqual(dados.uf, 'SP')
        self.assertEqual(dados.cnpj_emitente, '12345678000195')
        self.assertEqual(dados.modelo, '65')
        self.assertEqual(dados.numero, '12345')
        self.assertEqual(dados.serie, '1')
        self.assertEqual(dados.data_emissao, date(2026, 4, 1))
        self.assertIsNone(dados.valor_total)
        self.assertEqual(dados.url_consulta, URL_ONLINE)

    def test_qrcode_offline_traz_dia_e_valor(self):
        url = f'https://www.sefaz.rs.gov.br/NFCE/NFCE-COM.aspx?p={CHAVE}|2|1|14|58.43|6A6B|1|HASH'
        dados = interpretar_qrcode_nfce(url)
        self.assertEqual(dados.valor_total, Decimal('58.43'))
        self.assertEqual(dados.data_emissao, date(2026, 4, 14))

    def test_qrcode_versao_1_com_valor_e_data_em_hex(self):
        dh_emi = '2026-04-14T18:22:31-03:00'.encode('ascii').hex()
        url = f'http://www.fazenda.pr.gov.br/nfce/qrcode?chNFe={CHAVE}&nVersao=100&tpAmb=1&dhEmi={dh_emi}&vNF=58.43&vICMS=0.00'
        dados = interpretar_qrcode_nfce(url)
        self.assertEqual(dados.valor_total, Decimal('58.43'))
        self.assertEqual(dados.data_emissao, date(2026, 4, 14))

    def test_aceita_chave_digitada_com_espacos(self):
        espacada = ' '.join(CHAVE[i:i + 4] for i in range(0, 44, 4))
        self.assertEqual(interpretar_qrcode_nfce(espacada).chave_acesso, CHAVE)

    def test_rejeita_qrcode_que_nao_e_nota(self):
        with self.assertRaises(QRCodeNFCeInvalido):
            interpretar_qrcode_nfce('https://exemplo.com/cardapio')
        with self.assertRaises(QRCodeNFCeInvalido):
            interpretar_qrcode_nfce('')


class ConsultaSefazTests(SimpleTestCase):
    def test_extrai_loja_itens_total_e_data_do_layout_padrao(self):
        extraido = extrair_dados_pagina_sefaz(HTML_SEFAZ)
        self.assertEqual(extraido['fornecedor'], 'SUPERMERCADO EXEMPLO LTDA')
        self.assertEqual(extraido['valor_total'], Decimal('58.43'))
        self.assertEqual(extraido['data_emissao'], date(2026, 4, 14))
        self.assertEqual(len(extraido['itens']), 2)
        arroz, banana = extraido['itens']
        self.assertEqual((arroz.descricao, arroz.quantidade, arroz.unidade), ('ARROZ TIPO 1 5KG', Decimal('2'), 'UN'))
        self.assertEqual((arroz.valor_unitario, arroz.valor_total), (Decimal('24.90'), Decimal('49.80')))
        self.assertEqual((banana.quantidade, banana.unidade, banana.valor_total), (Decimal('1.235'), 'KG', Decimal('8.63')))

    @patch('core.services.nfce._baixar_pagina', return_value=HTML_SEFAZ)
    def test_consultar_completa_os_dados_do_qrcode(self, _baixar):
        dados = consultar_nfce(interpretar_qrcode_nfce(URL_ONLINE))
        self.assertTrue(dados.consulta_sefaz_ok)
        self.assertEqual(dados.fornecedor, 'SUPERMERCADO EXEMPLO LTDA')
        self.assertEqual(dados.valor_total, Decimal('58.43'))
        self.assertEqual(dados.data_emissao, date(2026, 4, 14))
        self.assertEqual(dados.aviso_consulta, '')

    @patch('core.services.nfce.buscar_nome_empresa', return_value='MERCADO DO CNPJ')
    @patch('core.services.nfce._baixar_pagina', side_effect=error.URLError('timeout'))
    def test_falha_na_sefaz_mantem_dados_do_qrcode_com_aviso(self, _baixar, buscar_nome):
        dados = consultar_nfce(interpretar_qrcode_nfce(URL_ONLINE))
        self.assertFalse(dados.consulta_sefaz_ok)
        self.assertEqual(dados.chave_acesso, CHAVE)
        self.assertIn('SEFAZ não respondeu', dados.aviso_consulta)
        buscar_nome.assert_called_once_with('12345678000195')
        self.assertEqual(dados.fornecedor, 'MERCADO DO CNPJ')

    @patch('core.services.nfce.buscar_nome_empresa', return_value='')
    @patch('core.services.nfce._baixar_pagina')
    def test_nao_acessa_links_fora_de_gov_br(self, baixar, _buscar_nome):
        dados = consultar_nfce(interpretar_qrcode_nfce(f'https://golpe.example.com/?p={CHAVE}|2|1|1|X'))
        baixar.assert_not_called()
        self.assertIn('.gov.br', dados.aviso_consulta)

    @patch('core.services.nfce.buscar_nome_empresa', return_value='MERCADINHO VILELA')
    @patch('core.services.nfce._baixar_pagina', return_value=HTML_MG_CAPTCHA)
    def test_portal_com_nao_sou_robo_usa_nome_do_cnpj_e_avisa(self, _baixar, _buscar_nome):
        dados = consultar_nfce(interpretar_qrcode_nfce(URL_MG))
        self.assertFalse(dados.consulta_sefaz_ok)
        self.assertTrue(dados.sefaz_pede_verificacao)
        self.assertIn('não sou robô', dados.aviso_consulta)
        self.assertIn('de MG', dados.aviso_consulta)
        self.assertEqual(dados.fornecedor, 'MERCADINHO VILELA')
        self.assertIsNone(dados.valor_total)

    @patch('core.services.nfce.buscar_nome_empresa')
    @patch('core.services.nfce._baixar_pagina', return_value=HTML_SEFAZ)
    def test_nao_consulta_cnpj_quando_a_sefaz_traz_a_loja(self, _baixar, buscar_nome):
        consultar_nfce(interpretar_qrcode_nfce(URL_ONLINE))
        buscar_nome.assert_not_called()


class BuscarNomeEmpresaTests(SimpleTestCase):
    def _resposta(self, corpo):
        resposta = MagicMock()
        resposta.__enter__.return_value.read.return_value = json.dumps(corpo).encode('utf-8')
        return resposta

    def test_prefere_nome_fantasia(self):
        with patch('core.services.nfce.request.urlopen', return_value=self._resposta(
            {'razao_social': 'MERCADINHO VILELA LTDA', 'nome_fantasia': 'MERCADINHO VILELA'}
        )) as urlopen:
            self.assertEqual(buscar_nome_empresa('23960651000129'), 'MERCADINHO VILELA')
        self.assertIn('/cnpj/v1/23960651000129', urlopen.call_args[0][0].full_url)

    def test_sem_fantasia_usa_razao_social(self):
        with patch('core.services.nfce.request.urlopen', return_value=self._resposta(
            {'razao_social': 'MERCADINHO VILELA LTDA', 'nome_fantasia': ''}
        )):
            self.assertEqual(buscar_nome_empresa('23960651000129'), 'MERCADINHO VILELA LTDA')

    def test_falha_ou_cnpj_invalido_devolve_vazio(self):
        with patch('core.services.nfce.request.urlopen', side_effect=error.URLError('fora')):
            self.assertEqual(buscar_nome_empresa('23960651000129'), '')
        with patch('core.services.nfce.request.urlopen') as urlopen:
            self.assertEqual(buscar_nome_empresa('123'), '')
            urlopen.assert_not_called()

    def test_sessao_ida_e_volta_preserva_os_dados(self):
        with patch('core.services.nfce._baixar_pagina', return_value=HTML_SEFAZ):
            dados = consultar_nfce(interpretar_qrcode_nfce(URL_ONLINE))
        from core.services.nfce import DadosNFCe
        copia = DadosNFCe.da_sessao(dados.para_sessao())
        self.assertEqual(copia, dados)


@patch('core.services.nfce._baixar_pagina', return_value=HTML_SEFAZ)
class ComprasQRCodeViewTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(username='compras_qr', password='123456')
        self.user.groups.add(Group.objects.get_or_create(name='Compras')[0])
        self.client.force_login(self.user)

    def _ler(self):
        return self.client.post(reverse('compras_qrcode'), {'acao': 'ler', 'conteudo_qrcode': URL_ONLINE})

    def _confirmar(self, **extra):
        dados = {
            'acao': 'confirmar',
            'fornecedor': 'SUPERMERCADO EXEMPLO LTDA',
            'descricao': 'Compra com 2 itens',
            'data_emissao': '2026-04-14',
            'valor_total': '58.43',
            'modo': 'total',
            'categoria_compra': 'geral',
            'tipo_item': 'Bem de Consumo',
            'cobrar_no_aluguel': 'on',
            'status': 'pendente',
            'forma_pagamento': '',
        }
        dados.update(extra)
        return self.client.post(reverse('compras_qrcode'), dados)

    def test_pagina_de_leitura_abre(self, _baixar):
        response = self.client.get(reverse('compras_qrcode'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Abrir câmera')
        self.assertContains(response, 'jsQR.js')

    def test_leitura_mostra_previa_preenchida(self, _baixar):
        response = self._ler()
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'SUPERMERCADO EXEMPLO LTDA')
        self.assertContains(response, 'ARROZ TIPO 1 5KG')
        self.assertContains(response, '12.345.678/0001-95')
        self.assertContains(response, 'value="58.43"')
        self.assertContains(response, 'value="2026-04-14"')
        self.assertEqual(NotaFiscal.objects.count(), 0)

    def test_confirmar_registra_compra_com_total_e_parcela(self, _baixar):
        self._ler()
        response = self._confirmar()
        self.assertRedirects(response, reverse('compras') + '?mes=2026-05', fetch_redirect_response=False)
        nota = NotaFiscal.objects.get()
        self.assertEqual(nota.setor, 'compras')
        self.assertEqual(nota.fornecedor, 'SUPERMERCADO EXEMPLO LTDA')
        self.assertEqual(nota.valor, Decimal('58.43'))
        self.assertEqual(nota.quantidade, 1)
        self.assertEqual(nota.chave_acesso, CHAVE)
        self.assertFalse(nota.adicionar_estoque)
        self.assertTrue(nota.cobrar_no_aluguel)
        self.assertIn('ARROZ TIPO 1 5KG', nota.observacao)
        parcela = nota.parcelas.get()
        self.assertEqual(parcela.valor, Decimal('58.43'))
        self.assertEqual(parcela.mes_referencia, date(2026, 5, 1))

    def test_confirmar_por_item_cria_um_registro_por_item(self, _baixar):
        self._ler()
        self._confirmar(modo='itens')
        notas = {n.descricao: n for n in NotaFiscal.objects.all()}
        self.assertEqual(len(notas), 2)
        arroz = notas['ARROZ TIPO 1 5KG']
        self.assertEqual((arroz.quantidade, arroz.valor), (2, Decimal('24.90')))
        banana = notas['BANANA PRATA (1,235 KG)']
        self.assertEqual((banana.quantidade, banana.valor), (1, Decimal('8.63')))
        self.assertEqual(sum(p.valor for n in notas.values() for p in n.parcelas.all()), Decimal('58.43'))

    def test_nota_ja_registrada_nao_duplica(self, _baixar):
        self._ler()
        self._confirmar()
        nota = NotaFiscal.objects.get()
        response = self._ler()
        self.assertRedirects(response, reverse('editar_nota_compra', args=[nota.id]), fetch_redirect_response=False)
        self.assertEqual(NotaFiscal.objects.count(), 1)

    def test_qrcode_invalido_mostra_erro(self, _baixar):
        response = self.client.post(reverse('compras_qrcode'), {'acao': 'ler', 'conteudo_qrcode': 'qualquer coisa'})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'chave de acesso válida')

    def test_confirmar_sem_leitura_volta_para_inicio(self, _baixar):
        response = self._confirmar()
        self.assertRedirects(response, reverse('compras_qrcode'), fetch_redirect_response=False)
        self.assertEqual(NotaFiscal.objects.count(), 0)

    def test_nota_de_mg_com_nao_sou_robo_mostra_link_e_pede_valor(self, baixar):
        baixar.return_value = HTML_MG_CAPTCHA
        with patch('core.services.nfce.buscar_nome_empresa', return_value='MERCADINHO VILELA'):
            response = self.client.post(reverse('compras_qrcode'), {'acao': 'ler', 'conteudo_qrcode': URL_MG})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'não sou robô')
        self.assertContains(response, 'value="MERCADINHO VILELA"')
        self.assertContains(response, 'Abrir a nota na SEFAZ')
        self.assertContains(response, 'href="https://portalsped.fazenda.mg.gov.br/portalnfce/sistema/qrcode.xhtml?p=')
        self.assertContains(response, 'Colar nota copiada')
        self.assertContains(response, '23.960.651/0001-29')

    def _ler_mg(self, baixar):
        baixar.return_value = HTML_MG_CAPTCHA
        with patch('core.services.nfce.buscar_nome_empresa', return_value='MERCADINHO VILELA'):
            self.client.post(reverse('compras_qrcode'), {'acao': 'ler', 'conteudo_qrcode': URL_MG})

    def test_colar_texto_da_nota_preenche_itens_e_registra(self, baixar):
        self._ler_mg(baixar)
        response = self.client.post(reverse('compras_qrcode'), {'acao': 'colar', 'texto_nota': TEXTO_MG_COPIADO})
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Nota lida: 3 item(ns).')
        self.assertContains(response, 'CERVEJA LATA 350ML')
        self.assertContains(response, 'value="1292.99"')
        self.assertContains(response, 'value="2026-11-14"')
        self.assertContains(response, 'value="MERCADINHO VILELA LTDA"')
        self.assertNotContains(response, 'Colar nota copiada')
        self._confirmar(modo='itens', fornecedor='MERCADINHO VILELA LTDA', data_emissao='2026-11-14', valor_total='1292.99')
        notas = {n.descricao: n for n in NotaFiscal.objects.all()}
        self.assertEqual(set(notas), {'ARROZ TIPO 1 5KG', 'BANANA PRATA (1,235 KG)', 'CERVEJA LATA 350ML'})
        self.assertEqual((notas['CERVEJA LATA 350ML'].quantidade, notas['CERVEJA LATA 350ML'].valor), (12, Decimal('102.88')))
        self.assertTrue(all(n.chave_acesso == CHAVE_MG for n in notas.values()))

    def test_colar_texto_errado_mantem_os_passos_com_erro(self, baixar):
        self._ler_mg(baixar)
        response = self.client.post(reverse('compras_qrcode'), {'acao': 'colar', 'texto_nota': 'Não sou um robô'})
        self.assertContains(response, 'Não achei itens nem valor')
        self.assertContains(response, 'Colar nota copiada')
        self.assertEqual(NotaFiscal.objects.count(), 0)

    def test_leitura_completa_nao_mostra_link_da_sefaz(self, _baixar):
        response = self._ler()
        self.assertNotContains(response, 'Abrir a nota na SEFAZ')

    def test_quem_so_visualiza_compras_nao_registra(self, _baixar):
        leitor = User.objects.create_user(username='so_ve', password='123456')
        Morador.objects.create(nome='So Ve', user=leitor, acesso_compras_visualizar=True)
        self.client.force_login(leitor)
        response = self._ler()
        self.assertEqual(response.status_code, 403)

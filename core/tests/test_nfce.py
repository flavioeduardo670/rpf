from datetime import date
from decimal import Decimal
from unittest.mock import patch
from urllib import error

from django.contrib.auth.models import Group, User
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from core.models import Morador, NotaFiscal
from core.services.nfce import (
    QRCodeNFCeInvalido,
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


class InterpretarQRCodeTests(SimpleTestCase):
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

    @patch('core.services.nfce._baixar_pagina', side_effect=error.URLError('timeout'))
    def test_falha_na_sefaz_mantem_dados_do_qrcode_com_aviso(self, _baixar):
        dados = consultar_nfce(interpretar_qrcode_nfce(URL_ONLINE))
        self.assertFalse(dados.consulta_sefaz_ok)
        self.assertEqual(dados.chave_acesso, CHAVE)
        self.assertIn('SEFAZ não respondeu', dados.aviso_consulta)

    @patch('core.services.nfce._baixar_pagina')
    def test_nao_acessa_links_fora_de_gov_br(self, baixar):
        dados = consultar_nfce(interpretar_qrcode_nfce(f'https://golpe.example.com/?p={CHAVE}|2|1|1|X'))
        baixar.assert_not_called()
        self.assertIn('.gov.br', dados.aviso_consulta)

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

    def test_quem_so_visualiza_compras_nao_registra(self, _baixar):
        leitor = User.objects.create_user(username='so_ve', password='123456')
        Morador.objects.create(nome='So Ve', user=leitor, acesso_compras_visualizar=True)
        self.client.force_login(leitor)
        response = self._ler()
        self.assertEqual(response.status_code, 403)

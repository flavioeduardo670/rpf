/**
 * Envia relatório de aluguel por morador usando a API do ERP.
 *
 * Como usar:
 * 1) Ajuste BASE_URL e API_KEY abaixo.
 * 2) No Google Apps Script, execute a função enviarRelatorioAluguelPorEmail().
 * 3) (Opcional) Crie um gatilho mensal para disparo automático.
 */
const ERP_CONFIG = {
  BASE_URL: 'https://SEU-ERP.onrender.com',
  // IMPORTANTE: aqui vai o VALOR da chave, não o texto "X-API-Key".
  API_KEY: 'SUA_ERP_API_KEY',
  // Formato: YYYY-MM. Exemplo: '2026-04'. Se vazio, usa mês atual do ERP.
  MES_REFERENCIA: '',
};

function enviarRelatorioAluguelPorEmail() {
  validarConfiguracao_();
  const payload = consultarApi_();
  const mesReferencia = payload.mes_referencia || (ERP_CONFIG.MES_REFERENCIA + '-01');
  const moradores = payload.moradores || [];

  moradores.forEach(function (item) {
    // Regra solicitada: sem e-mail cadastrado, ignora.
    if (!item.email) return;

    const nome = item.apelido || item.nome;
    const assunto = 'Relatório de aluguel - ' + formatarMesAno(mesReferencia);
    const corpoTexto = montarRelatorioTexto(nome, item, mesReferencia);
    const corpoHtml = montarRelatorioHtml(nome, item, mesReferencia);

    MailApp.sendEmail({
      to: item.email,
      subject: assunto,
      body: corpoTexto,
      htmlBody: corpoHtml,
    });
  });
}

function validarConfiguracao_() {
  if (!ERP_CONFIG.BASE_URL || ERP_CONFIG.BASE_URL.indexOf('SEU-ERP') !== -1) {
    throw new Error('Configure ERP_CONFIG.BASE_URL com a URL real do seu ERP.');
  }
  if (!ERP_CONFIG.API_KEY || ERP_CONFIG.API_KEY === 'X-API-Key' || ERP_CONFIG.API_KEY.indexOf('SUA_') === 0) {
    throw new Error('Configure ERP_CONFIG.API_KEY com o valor real de ERP_API_KEY (não o nome do header).');
  }
}

function consultarApi_() {
  const mesParam = ERP_CONFIG.MES_REFERENCIA
    ? '&mes=' + encodeURIComponent(ERP_CONFIG.MES_REFERENCIA)
    : '';
  const baseUrl = ERP_CONFIG.BASE_URL.replace(/\/+$/, '');
  const endpoints = [
    '/api/setores/financeiro?rateio=1' + mesParam,
    '/api/financeiro?rateio=1' + mesParam,
    '/api/setores/financeiro/rateio/' + (ERP_CONFIG.MES_REFERENCIA ? '?mes=' + encodeURIComponent(ERP_CONFIG.MES_REFERENCIA) : ''),
    '/api/financeiro/rateio/' + (ERP_CONFIG.MES_REFERENCIA ? '?mes=' + encodeURIComponent(ERP_CONFIG.MES_REFERENCIA) : ''),
    '/api/setores/financeiro/rateio' + (ERP_CONFIG.MES_REFERENCIA ? '?mes=' + encodeURIComponent(ERP_CONFIG.MES_REFERENCIA) : ''),
    '/api/financeiro/rateio' + (ERP_CONFIG.MES_REFERENCIA ? '?mes=' + encodeURIComponent(ERP_CONFIG.MES_REFERENCIA) : ''),
  ];

  let ultimoErro = 'Nenhuma resposta da API.';
  for (let i = 0; i < endpoints.length; i++) {
    const endpoint = baseUrl + endpoints[i];
    const response = UrlFetchApp.fetch(endpoint, {
      method: 'get',
      muteHttpExceptions: true,
      followRedirects: true,
      headers: {
        'X-API-Key': ERP_CONFIG.API_KEY,
        'Accept': 'application/json',
      },
    });

    const status = response.getResponseCode();
    const body = response.getContentText();

    if (status === 200) {
      return JSON.parse(body);
    }

    ultimoErro = 'Erro HTTP ' + status + ' em ' + endpoint + ' | ' + body;
  }

  throw new Error(ultimoErro);
}

function montarRelatorioTexto(nome, item, mesReferencia) {
  return [
    'Olá, ' + nome + '!',
    '',
    'Segue seu relatório de aluguel referente a ' + formatarMesAno(mesReferencia) + ':',
    '',
    'Aluguel: R$ ' + formatarMoeda(item.aluguel),
    'Contas fixas: R$ ' + formatarMoeda(item.fixas),
    'Caixinha: R$ ' + formatarMoeda(item.caixinha),
    'Parcelas: R$ ' + formatarMoeda(item.parcelas),
    'Desconto: R$ ' + formatarMoeda(item.desconto),
    'Extra: R$ ' + formatarMoeda(item.extra),
    'Total do mês: R$ ' + formatarMoeda(item.valor_total),
    '',
    'Mensagem automática do ERP.',
  ].join('\n');
}

function montarRelatorioHtml(nome, item, mesReferencia) {
  return (
    '<p>Olá, <strong>' + escaparHtml(nome) + '</strong>!</p>' +
    '<p>Segue seu relatório de aluguel referente a <strong>' + formatarMesAno(mesReferencia) + '</strong>:</p>' +
    '<table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse;font-family:Arial,sans-serif;">' +
    '<tr><td><strong>Aluguel</strong></td><td>R$ ' + formatarMoeda(item.aluguel) + '</td></tr>' +
    '<tr><td><strong>Contas fixas</strong></td><td>R$ ' + formatarMoeda(item.fixas) + '</td></tr>' +
    '<tr><td><strong>Caixinha</strong></td><td>R$ ' + formatarMoeda(item.caixinha) + '</td></tr>' +
    '<tr><td><strong>Parcelas</strong></td><td>R$ ' + formatarMoeda(item.parcelas) + '</td></tr>' +
    '<tr><td><strong>Desconto</strong></td><td>R$ ' + formatarMoeda(item.desconto) + '</td></tr>' +
    '<tr><td><strong>Extra</strong></td><td>R$ ' + formatarMoeda(item.extra) + '</td></tr>' +
    '<tr><td><strong>Total do mês</strong></td><td><strong>R$ ' + formatarMoeda(item.valor_total) + '</strong></td></tr>' +
    '</table>' +
    '<p style="color:#666;">Mensagem automática do ERP.</p>'
  );
}

function formatarMesAno(dataIso) {
  const data = new Date(dataIso);
  return Utilities.formatDate(data, Session.getScriptTimeZone(), 'MM/yyyy');
}

function formatarMoeda(valor) {
  const numero = Number(valor || 0);
  return numero.toFixed(2).replace('.', ',');
}

function escaparHtml(texto) {
  return String(texto || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

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
  API_KEY: 'SUA_ERP_API_KEY',
  // Formato: YYYY-MM. Exemplo: '2026-04'. Se vazio, usa mês atual do ERP.
  MES_REFERENCIA: '',
};

function enviarRelatorioAluguelPorEmail() {
  const mesParam = ERP_CONFIG.MES_REFERENCIA
    ? '?mes=' + encodeURIComponent(ERP_CONFIG.MES_REFERENCIA)
    : '';
  const endpoint = ERP_CONFIG.BASE_URL + '/api/setores/financeiro/rateio/' + mesParam;

  const response = UrlFetchApp.fetch(endpoint, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      'X-API-Key': ERP_CONFIG.API_KEY,
      'Accept': 'application/json',
    },
  });

  const status = response.getResponseCode();
  if (status !== 200) {
    throw new Error('Erro ao consultar API do ERP. HTTP ' + status + ' | ' + response.getContentText());
  }

  const payload = JSON.parse(response.getContentText());
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
  const valor = String(dataIso || '').trim();
  const partes = valor.split('-');

  if (partes.length >= 2) {
    const ano = Number(partes[0]);
    const mes = Number(partes[1]);
    const dia = partes.length >= 3 ? Number(partes[2]) : 1;

    if (!isNaN(ano) && !isNaN(mes) && !isNaN(dia)) {
      const dataLocal = new Date(ano, mes - 1, dia);
      return Utilities.formatDate(dataLocal, Session.getScriptTimeZone(), 'MM/yyyy');
    }
  }

  const dataFallback = new Date(valor);
  if (!isNaN(dataFallback.getTime())) {
    return Utilities.formatDate(dataFallback, Session.getScriptTimeZone(), 'MM/yyyy');
  }

  return valor;
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

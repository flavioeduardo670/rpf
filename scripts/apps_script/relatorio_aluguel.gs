/**
 * Integração completa ERP -> Google Apps Script para envio de relatório mensal de aluguel.
 *
 * Passo a passo:
 * 1) Preencha ERP_CONFIG com BASE_URL + API_KEY + e-mail de fallback (opcional).
 * 2) Salve e execute testarConexaoERP() para validar endpoints.
 * 3) Execute enviarRelatorioAluguelPorEmail() para disparar os e-mails.
 * 4) (Opcional) Crie um gatilho mensal para enviarRelatorioAluguelPorEmail.
 */
const ERP_CONFIG = {
  BASE_URL: 'https://SEU-ERP.onrender.com',
  API_KEY: 'SUA_ERP_API_KEY',
  // Formato YYYY-MM. Ex.: '2026-04'. Se vazio, usa mês atual no backend.
  MES_REFERENCIA: '',
  // Opcional: recebe alertas quando houver erro crítico.
  EMAIL_ALERTA: '',
  REQUEST_TIMEOUT_SECONDS: 30,
};

const ERP_ENDPOINTS_RATEIO = [
  '/api/setores/financeiro/rateio/',
  '/api/setores/financeiro/rateio',
  '/api/financeiro/rateio/',
  '/api/financeiro/rateio',
  '/api/finnaceiro/rateio/', // typo comum
  '/api/finnaceiro/rateio',
  '/api/rateio/',
  '/api/rateio',
];

function enviarRelatorioAluguelPorEmail() {
  validarConfiguracao();

  try {
    executarDiagnosticoBasico();
    const payload = buscarRateioMensal();
    const mesReferencia = obterMesReferencia(payload);
    const moradores = payload.moradores || [];

    if (!moradores.length) {
      Logger.log('Nenhum morador retornado para o mês ' + formatarMesAno(mesReferencia) + '.');
      return;
    }

    let enviados = 0;
    let ignoradosSemEmail = 0;

    moradores.forEach(function (item) {
      if (!item.email) {
        ignoradosSemEmail += 1;
        return;
      }

      const nome = item.apelido || item.nome || 'morador';
      const assunto = 'Relatório de aluguel - ' + formatarMesAno(mesReferencia);
      const corpoTexto = montarRelatorioTexto(nome, item, mesReferencia);
      const corpoHtml = montarRelatorioHtml(nome, item, mesReferencia);

      MailApp.sendEmail({
        to: item.email,
        subject: assunto,
        body: corpoTexto,
        htmlBody: corpoHtml,
      });
      enviados += 1;
    });

    Logger.log(
      'Relatórios enviados: ' + enviados +
      ' | ignorados sem e-mail: ' + ignoradosSemEmail +
      ' | mês: ' + formatarMesAno(mesReferencia)
    );
  } catch (error) {
    registrarErroCritico(error);
    throw error;
  }
}


function executarDiagnosticoBasico() {
  const baseUrl = normalizarBaseUrl(ERP_CONFIG.BASE_URL);

  // Endpoints de diagnóstico são opcionais para manter compatibilidade com deploys antigos.
  const statusResp = requestJson(baseUrl + '/api/status/');
  if (statusResp.status !== 200 && statusResp.status !== 404) {
    Logger.log('Aviso: /api/status/ respondeu HTTP ' + statusResp.status);
  }

  const authResp = requestJson(baseUrl + '/api/auth-check/');
  if (authResp.status === 401 || authResp.status === 403) {
    throw new Error('API key inválida ou ausente no servidor (/api/auth-check/). HTTP ' + authResp.status);
  }

  if (authResp.status !== 200 && authResp.status !== 404) {
    Logger.log('Aviso: /api/auth-check/ respondeu HTTP ' + authResp.status);
  }
}


function testarConexaoERP() {
  validarConfiguracao();

  const tentativas = montarTentativasEndpoint();
  const resultados = [];

  tentativas.forEach(function (tentativa) {
    const resposta = requestJson(tentativa.url);
    resultados.push({
      endpoint: tentativa.url,
      status: resposta.status,
      ok: resposta.status === 200,
    });
  });

  Logger.log(JSON.stringify(resultados, null, 2));
  return resultados;
}

function buscarRateioMensal() {
  const tentativas = montarTentativasEndpoint();
  let ultimoErro = null;

  for (let i = 0; i < tentativas.length; i += 1) {
    const tentativa = tentativas[i];
    const resposta = requestJson(tentativa.url);

    if (resposta.status === 200) {
      if (resposta.json && resposta.json.moradores) {
        return resposta.json;
      }
      throw new Error('API respondeu 200 mas sem estrutura esperada em ' + tentativa.url);
    }

    if (resposta.status === 401 || resposta.status === 403) {
      throw new Error('Falha de autenticação na API (verifique API_KEY). Endpoint: ' + tentativa.url);
    }

    if (resposta.status === 503) {
      throw new Error('API indisponível (ERP_API_KEY ausente no servidor). Endpoint: ' + tentativa.url);
    }

    ultimoErro = new Error('Endpoint não disponível: ' + tentativa.url + ' | HTTP ' + resposta.status);
  }

  throw ultimoErro || new Error('Não foi possível localizar endpoint de rateio do ERP.');
}

function montarTentativasEndpoint() {
  const baseUrl = normalizarBaseUrl(ERP_CONFIG.BASE_URL);
  const mesParam = ERP_CONFIG.MES_REFERENCIA
    ? 'mes=' + encodeURIComponent(ERP_CONFIG.MES_REFERENCIA)
    : '';

  return ERP_ENDPOINTS_RATEIO.map(function (path) {
    const urlBase = baseUrl + path;
    const join = urlBase.indexOf('?') >= 0 ? '&' : '?';
    const url = mesParam ? urlBase + join + mesParam : urlBase;
    return { path: path, url: url };
  });
}

function requestJson(url) {
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      'X-API-Key': ERP_CONFIG.API_KEY,
      Accept: 'application/json',
    },
    timeout: ERP_CONFIG.REQUEST_TIMEOUT_SECONDS * 1000,
  });

  const status = response.getResponseCode();
  const body = response.getContentText();
  let parsed = null;

  if (body) {
    try {
      parsed = JSON.parse(body);
    } catch (e) {
      parsed = null;
    }
  }

  return {
    status: status,
    text: body,
    json: parsed,
  };
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

function obterMesReferencia(payload) {
  if (payload && payload.mes_referencia) {
    return payload.mes_referencia;
  }
  if (ERP_CONFIG.MES_REFERENCIA) {
    return ERP_CONFIG.MES_REFERENCIA + '-01';
  }
  const hoje = new Date();
  return Utilities.formatDate(hoje, Session.getScriptTimeZone(), 'yyyy-MM') + '-01';
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

function normalizarBaseUrl(url) {
  return String(url || '').trim().replace(/\/+$/, '');
}

function validarConfiguracao() {
  if (!normalizarBaseUrl(ERP_CONFIG.BASE_URL)) {
    throw new Error('ERP_CONFIG.BASE_URL não foi definido.');
  }
  if (!String(ERP_CONFIG.API_KEY || '').trim()) {
    throw new Error('ERP_CONFIG.API_KEY não foi definido.');
  }
}

function registrarErroCritico(error) {
  const mensagem = '[ERP][Apps Script] Falha ao enviar relatório: ' + (error && error.message ? error.message : error);
  Logger.log(mensagem);

  if (!ERP_CONFIG.EMAIL_ALERTA) {
    return;
  }

  MailApp.sendEmail({
    to: ERP_CONFIG.EMAIL_ALERTA,
    subject: 'Erro no envio de relatório de aluguel',
    body: mensagem,
  });
}

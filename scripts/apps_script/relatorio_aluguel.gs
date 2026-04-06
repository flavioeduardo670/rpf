/**
 * Google Apps Script para consumir a API de relatórios por página e
 * enviar por e-mail para moradores selecionados.
 *
 * Fluxo:
 * 1) Defina BASE_URL, API_KEY, PAGINA e MORADOR_IDS.
 * 2) Execute enviarRelatorioPaginaPorEmail().
 */
const ERP_CONFIG = {
  BASE_URL: 'https://SEU-ERP.onrender.com',
  API_KEY: 'SUA_ERP_API_KEY',
  // Opções: home, calendario, perfil, moradores, financeiro, compras, rock, almoxarifado, manutencao
  PAGINA: 'financeiro',
  // IDs dos moradores que devem receber o e-mail.
  MORADOR_IDS: [1, 2],
};

function enviarRelatorioPaginaPorEmail() {
  validarConfiguracao();

  const endpoint =
    ERP_CONFIG.BASE_URL.replace(/\/$/, '') +
    '/api/paginas/' +
    encodeURIComponent(ERP_CONFIG.PAGINA) +
    '/relatorio/';

  const response = UrlFetchApp.fetch(endpoint, {
    method: 'post',
    contentType: 'application/json',
    muteHttpExceptions: true,
    payload: JSON.stringify({
      moradores: ERP_CONFIG.MORADOR_IDS,
    }),
    headers: {
      'X-API-Key': ERP_CONFIG.API_KEY,
      Accept: 'application/json',
    },
  });

  const status = response.getResponseCode();
  if (status !== 200) {
    throw new Error(
      'Erro ao gerar relatório. HTTP ' + status + ' | ' + response.getContentText()
    );
  }

  const payload = JSON.parse(response.getContentText());
  const relatorios = payload.relatorios || [];

  relatorios.forEach(function (item) {
    const morador = item.morador || {};
    if (!morador.email) return;

    MailApp.sendEmail({
      to: morador.email,
      subject: item.assunto,
      body: item.corpo_texto,
      htmlBody: item.corpo_html,
    });
  });
}

function listarPaginasDisponiveis() {
  const endpoint = ERP_CONFIG.BASE_URL.replace(/\/$/, '') + '/api/paginas/';
  const response = UrlFetchApp.fetch(endpoint, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      'X-API-Key': ERP_CONFIG.API_KEY,
      Accept: 'application/json',
    },
  });

  const status = response.getResponseCode();
  if (status !== 200) {
    throw new Error('Erro ao listar páginas. HTTP ' + status + ' | ' + response.getContentText());
  }

  return JSON.parse(response.getContentText());
}

function listarMoradoresDisponiveis() {
  const endpoint = ERP_CONFIG.BASE_URL.replace(/\/$/, '') + '/api/moradores/';
  const response = UrlFetchApp.fetch(endpoint, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      'X-API-Key': ERP_CONFIG.API_KEY,
      Accept: 'application/json',
    },
  });

  const status = response.getResponseCode();
  if (status !== 200) {
    throw new Error('Erro ao listar moradores. HTTP ' + status + ' | ' + response.getContentText());
  }

  return JSON.parse(response.getContentText());
}

function validarConfiguracao() {
  if (!ERP_CONFIG.BASE_URL || ERP_CONFIG.BASE_URL.indexOf('http') !== 0) {
    throw new Error('Configure ERP_CONFIG.BASE_URL com a URL do seu ERP.');
  }
  if (!ERP_CONFIG.API_KEY) {
    throw new Error('Configure ERP_CONFIG.API_KEY.');
  }
  if (!ERP_CONFIG.PAGINA) {
    throw new Error('Configure ERP_CONFIG.PAGINA.');
  }
  if (!Array.isArray(ERP_CONFIG.MORADOR_IDS) || ERP_CONFIG.MORADOR_IDS.length === 0) {
    throw new Error('Configure ERP_CONFIG.MORADOR_IDS com ao menos um ID.');
  }
}

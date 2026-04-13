/**
 * Cliente Apps Script para consumir dados do sistema RPF (Django).
 *
 * Fluxo:
 * 1) Faz login em /login/ com usuário e senha (capturando CSRF + cookies de sessão).
 * 2) Chama endpoints de exportação CSV autenticados.
 * 3) Grava os dados em abas do Google Sheets.
 */
const RPF_API_CONFIG = {
  BASE_URL: 'https://SEU-RPF.exemplo.com',
  USERNAME: 'SEU_USUARIO',
  PASSWORD: 'SUA_SENHA',
  TIMEZONE: 'America/Sao_Paulo',
  SHEETS: {
    MORADORES: 'rpf_moradores',
    FINANCEIRO: 'rpf_financeiro',
    COMPRAS: 'rpf_compras',
    ESTOQUE: 'rpf_estoque',
    CONSUMO: 'rpf_consumo',
  },
  PROPERTY_KEYS: {
    USERNAME: 'RPF_USERNAME',
    PASSWORD: 'RPF_PASSWORD',
  },
};

function sincronizarRpfCsvs() {
  const session = rpfLogin_();

  const moradores = fetchCsvRows_('/moradores/exportar/', session);
  const financeiro = fetchCsvRows_('/financeiro/exportar/', session, {
    mes: Utilities.formatDate(new Date(), RPF_API_CONFIG.TIMEZONE, 'yyyy-MM'),
  });
  const compras = fetchCsvRows_('/compras/exportar/', session);
  const estoque = fetchCsvRows_('/almoxarifado/exportar/', session);
  const consumo = fetchCsvRows_('/almoxarifado/consumo/exportar/', session);

  writeCsvToSheet_(RPF_API_CONFIG.SHEETS.MORADORES, moradores);
  writeCsvToSheet_(RPF_API_CONFIG.SHEETS.FINANCEIRO, financeiro);
  writeCsvToSheet_(RPF_API_CONFIG.SHEETS.COMPRAS, compras);
  writeCsvToSheet_(RPF_API_CONFIG.SHEETS.ESTOQUE, estoque);
  writeCsvToSheet_(RPF_API_CONFIG.SHEETS.CONSUMO, consumo);
}

function sincronizarFinanceiroPorMesRpf(mes) {
  if (!/^\d{4}-\d{2}$/.test(String(mes || ''))) {
    throw new Error('Parâmetro "mes" deve estar no formato YYYY-MM.');
  }

  const session = rpfLogin_();
  const financeiro = fetchCsvRows_('/financeiro/exportar/', session, { mes: mes });
  writeCsvToSheet_(RPF_API_CONFIG.SHEETS.FINANCEIRO, financeiro);
}

function rpfLogin_() {
  const loginUrl = buildRpfUrl_('/login/');
  const loginPageResponse = UrlFetchApp.fetch(loginUrl, {
    method: 'get',
    followRedirects: false,
    muteHttpExceptions: true,
  });

  const loginHtml = loginPageResponse.getContentText();
  const loginHeaders = loginPageResponse.getAllHeaders();
  const cookieJar = parseCookies_(loginHeaders['Set-Cookie']);

  const csrfToken = extractCsrfToken_(loginHtml, cookieJar);
  const username = getCredential_(RPF_API_CONFIG.PROPERTY_KEYS.USERNAME, RPF_API_CONFIG.USERNAME);
  const password = getCredential_(RPF_API_CONFIG.PROPERTY_KEYS.PASSWORD, RPF_API_CONFIG.PASSWORD);

  const payload = {
    username: username,
    password: password,
    csrfmiddlewaretoken: csrfToken,
    next: '/',
  };

  const loginPost = UrlFetchApp.fetch(loginUrl, {
    method: 'post',
    payload: payload,
    headers: {
      Cookie: toCookieHeader_(cookieJar),
      Referer: loginUrl,
    },
    followRedirects: false,
    muteHttpExceptions: true,
  });

  if (loginPost.getResponseCode() < 300 || loginPost.getResponseCode() >= 400) {
    throw new Error('Falha ao autenticar no RPF. HTTP ' + loginPost.getResponseCode());
  }

  const postCookies = parseCookies_(loginPost.getAllHeaders()['Set-Cookie']);
  const finalCookies = Object.assign({}, cookieJar, postCookies);

  return {
    cookieHeader: toCookieHeader_(finalCookies),
    csrfToken: csrfToken,
  };
}

function fetchCsvRows_(path, session, queryParams) {
  const url = buildRpfUrl_(path, queryParams || {});
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      Cookie: session.cookieHeader,
      Referer: buildRpfUrl_('/'),
      Accept: 'text/csv,*/*;q=0.8',
    },
  });

  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('Erro ao baixar CSV [' + status + '] ' + path + ' => ' + response.getContentText());
  }

  const raw = response.getContentText('UTF-8').replace(/^\uFEFF/, '');
  return Utilities.parseCsv(raw, ';');
}

function writeCsvToSheet_(sheetName, rows) {
  const sheet = getOrCreateSheetRpf_(sheetName);
  sheet.clear();

  if (!rows || !rows.length) {
    sheet.getRange(1, 1).setValue('Sem dados para o período.');
    return;
  }

  sheet.getRange(1, 1, rows.length, rows[0].length).setValues(rows);
  sheet.getRange(1, 1, 1, rows[0].length).setFontWeight('bold');
  sheet.autoResizeColumns(1, rows[0].length);
}

function getOrCreateSheetRpf_(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

function buildRpfUrl_(path, params) {
  const base = RPF_API_CONFIG.BASE_URL.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : '/' + path;
  const entries = Object.keys(params || {})
    .filter(function (k) { return params[k] !== null && params[k] !== undefined && params[k] !== ''; })
    .map(function (k) { return encodeURIComponent(k) + '=' + encodeURIComponent(params[k]); });
  return base + normalizedPath + (entries.length ? '?' + entries.join('&') : '');
}

function getCredential_(propertyKey, fallback) {
  const fromProperty = PropertiesService.getScriptProperties().getProperty(propertyKey);
  if (fromProperty) return fromProperty;
  if (!fallback) {
    throw new Error('Credencial ausente para ' + propertyKey + '. Configure Script Properties.');
  }
  return fallback;
}

function parseCookies_(setCookieHeader) {
  const out = {};
  const values = Array.isArray(setCookieHeader)
    ? setCookieHeader
    : (setCookieHeader ? [setCookieHeader] : []);

  values.forEach(function (line) {
    const firstPart = String(line || '').split(';')[0];
    const idx = firstPart.indexOf('=');
    if (idx <= 0) return;
    const name = firstPart.substring(0, idx).trim();
    const value = firstPart.substring(idx + 1).trim();
    if (name) out[name] = value;
  });

  return out;
}

function toCookieHeader_(cookieObj) {
  return Object.keys(cookieObj || {})
    .map(function (key) { return key + '=' + cookieObj[key]; })
    .join('; ');
}

function extractCsrfToken_(html, cookieJar) {
  const regex = /name=["']csrfmiddlewaretoken["']\s+value=["']([^"']+)["']/i;
  const match = String(html || '').match(regex);
  if (match && match[1]) return match[1];
  if (cookieJar && cookieJar.csrftoken) return cookieJar.csrftoken;
  throw new Error('Não foi possível encontrar token CSRF na página de login.');
}

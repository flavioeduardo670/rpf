const ERP_CONFIG = {
  BASE_URL: 'https://SEU-ERP.exemplo.com/api',
  BEARER_TOKEN: 'SEU_TOKEN_AQUI',
  // Opcional: se preenchido, usa Script Properties ao invés de hardcode.
  BEARER_TOKEN_PROPERTY_KEY: 'ERP_BEARER_TOKEN',
  TIMEZONE: 'America/Sao_Paulo',
  PAGE_SIZE: 200,
  HTTP_MAX_RETRIES: 3,
  HTTP_RETRY_SLEEP_MS: 800,
  FASE4: {
    LOCK_TIMEOUT_MS: 25000,
    OVERLAP_DAYS: 2,
    FULL_SYNC_DAYS: 60,
    SYNC_STATE_PROPERTY_KEY: 'FINANCEIRO_LAST_SUCCESS_DATE',
    LAST_STATUS_PROPERTY_KEY: 'FINANCEIRO_LAST_STATUS',
  },
  ALERT_THRESHOLDS: {
    INADIMPLENCIA_PCT: 8,
    SALDO_DIA_MINIMO: 0,
    DESVIO_CAIXA_PERCENTUAL: 20,
  },
  SHEETS: {
    RECEBER: 'base_receber',
    PAGAR: 'base_pagar',
    FLUXO: 'base_fluxo',
    KPIS: 'base_kpis',
    PAINEL: 'painel',
    PAINEL_DADOS: 'painel_dados',
    EXECUCAO: 'painel_execucao',
    ALERTAS: 'painel_alertas',
    ESTADO_SYNC: 'painel_estado_sync',
  },
};

function apiGet(path, queryParams) {
  const url = buildUrl(path, queryParams || {});
  return fetchJsonWithRetry_(url, path);
}

function fetchJsonWithRetry_(url, path) {
  const maxRetries = Number(ERP_CONFIG.HTTP_MAX_RETRIES || 1);
  const sleepMs = Number(ERP_CONFIG.HTTP_RETRY_SLEEP_MS || 0);
  let attempt = 1;
  let lastError = null;

  while (attempt <= maxRetries) {
    try {
      const response = UrlFetchApp.fetch(url, {
        method: 'get',
        muteHttpExceptions: true,
        headers: {
          Authorization: 'Bearer ' + getBearerToken_(),
          Accept: 'application/json',
        },
      });

      const status = response.getResponseCode();
      if (status >= 200 && status < 300) {
        return JSON.parse(response.getContentText());
      }

      if (status === 429 || status >= 500) {
        lastError = new Error('Erro transitório API [' + status + '] ' + path);
      } else {
        throw new Error('Erro API [' + status + '] ' + path + ' => ' + response.getContentText());
      }
    } catch (error) {
      lastError = error;
    }

    if (attempt < maxRetries && sleepMs > 0) {
      Utilities.sleep(sleepMs * attempt);
    }
    attempt += 1;
  }

  throw new Error('Falha após ' + maxRetries + ' tentativa(s): ' + String(lastError));
}

function fetchAllPages(path, baseParams) {
  let page = 1;
  const pageSize = ERP_CONFIG.PAGE_SIZE;
  const all = [];

  while (true) {
    const payload = apiGet(path, Object.assign({}, baseParams, {
      page: page,
      page_size: pageSize,
    }));

    const items = payload.items || payload.results || payload.data || [];
    all.push.apply(all, items);

    const hasNext = Boolean(payload.next);
    const totalPages = Number(payload.total_pages || 0);

    if (hasNext) {
      page += 1;
      continue;
    }

    if (totalPages && page < totalPages) {
      page += 1;
      continue;
    }

    if (!items.length || items.length < pageSize) {
      break;
    }

    page += 1;
  }

  return all;
}

function buildUrl(path, params) {
  const base = ERP_CONFIG.BASE_URL.replace(/\/$/, '');
  const normalizedPath = path.startsWith('/') ? path : '/' + path;
  const entries = Object.keys(params || {})
    .filter(function (key) {
      return params[key] !== undefined && params[key] !== null && params[key] !== '';
    })
    .map(function (key) {
      return encodeURIComponent(key) + '=' + encodeURIComponent(params[key]);
    });

  return base + normalizedPath + (entries.length ? '?' + entries.join('&') : '');
}

function getBearerToken_() {
  const propertyKey = ERP_CONFIG.BEARER_TOKEN_PROPERTY_KEY;
  if (propertyKey) {
    const fromProperty = PropertiesService.getScriptProperties().getProperty(propertyKey);
    if (fromProperty) return fromProperty;
  }

  if (!ERP_CONFIG.BEARER_TOKEN) {
    throw new Error('Token Bearer não configurado. Defina ERP_CONFIG.BEARER_TOKEN ou Script Properties.');
  }

  return ERP_CONFIG.BEARER_TOKEN;
}

const ERP_CONFIG = {
  BASE_URL: 'https://SEU-ERP.exemplo.com/api',
  BEARER_TOKEN: 'SEU_TOKEN_AQUI',
  TIMEZONE: 'America/Sao_Paulo',
  PAGE_SIZE: 200,
  SHEETS: {
    RECEBER: 'base_receber',
    PAGAR: 'base_pagar',
    FLUXO: 'base_fluxo',
    KPIS: 'base_kpis',
    PAINEL: 'painel',
    PAINEL_DADOS: 'painel_dados',
    EXECUCAO: 'painel_execucao',
  },
};

function apiGet(path, queryParams) {
  const url = buildUrl(path, queryParams || {});
  const response = UrlFetchApp.fetch(url, {
    method: 'get',
    muteHttpExceptions: true,
    headers: {
      Authorization: 'Bearer ' + ERP_CONFIG.BEARER_TOKEN,
      Accept: 'application/json',
    },
  });

  const status = response.getResponseCode();
  if (status < 200 || status >= 300) {
    throw new Error('Erro API [' + status + '] ' + path + ' => ' + response.getContentText());
  }

  return JSON.parse(response.getContentText());
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

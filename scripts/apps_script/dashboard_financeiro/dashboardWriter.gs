function escreverBaseReceber(rows) {
  writeSheetRows_(ERP_CONFIG.SHEETS.RECEBER,
    ['id_titulo', 'cliente', 'emissao', 'vencimento', 'valor_original', 'valor_aberto', 'valor_pago', 'status', 'centro_custo'],
    rows,
    function (r) {
      return [r.id_titulo, r.cliente, r.emissao, r.vencimento, r.valor_original, r.valor_aberto, r.valor_pago, r.status, r.centro_custo];
    });
}

function escreverBasePagar(rows) {
  writeSheetRows_(ERP_CONFIG.SHEETS.PAGAR,
    ['id_titulo', 'fornecedor', 'emissao', 'vencimento', 'valor_original', 'valor_aberto', 'valor_pago', 'status', 'categoria_despesa'],
    rows,
    function (r) {
      return [r.id_titulo, r.fornecedor, r.emissao, r.vencimento, r.valor_original, r.valor_aberto, r.valor_pago, r.status, r.categoria_despesa];
    });
}

function escreverBaseFluxo(rows) {
  writeSheetRows_(ERP_CONFIG.SHEETS.FLUXO,
    ['data', 'entradas_previstas', 'saidas_previstas', 'entradas_realizadas', 'saidas_realizadas', 'saldo_dia', 'saldo_acumulado'],
    rows,
    function (r) {
      return [r.data, r.entradas_previstas, r.saidas_previstas, r.entradas_realizadas, r.saidas_realizadas, r.saldo_dia, r.saldo_acumulado];
    });
}

function escreverBaseKpis(rows) {
  writeSheetRows_(ERP_CONFIG.SHEETS.KPIS,
    ['receita_mes', 'despesa_mes', 'resultado_mes', 'inadimplencia_valor', 'inadimplencia_percentual', 'prazo_medio_recebimento', 'prazo_medio_pagamento', 'atualizado_em'],
    rows,
    function (r) {
      return [r.receita_mes, r.despesa_mes, r.resultado_mes, r.inadimplencia_valor, r.inadimplencia_percentual, r.prazo_medio_recebimento, r.prazo_medio_pagamento, r.atualizado_em];
    });
}

function atualizarPainelComKpis(kpis) {
  const sheet = getOrCreateSheet_(ERP_CONFIG.SHEETS.PAINEL);
  sheet.clear();

  const cards = [
    ['Receita do mês', kpis.receita_mes],
    ['Despesa do mês', kpis.despesa_mes],
    ['Resultado do mês', kpis.resultado_mes],
    ['Inadimplência (R$)', kpis.inadimplencia_valor],
    ['Inadimplência (%)', kpis.inadimplencia_percentual],
  ];

  sheet.getRange(1, 1, 1, 2).setValues([['Indicador', 'Valor']]);
  sheet.getRange(2, 1, cards.length, 2).setValues(cards);
  sheet.getRange(1, 4).setValue('Atualizado em');
  sheet.getRange(2, 4).setValue(kpis.atualizado_em);

  sheet.getRange(1, 1, 1, 2).setFontWeight('bold');
  sheet.getRange(1, 4).setFontWeight('bold');
}

function atualizarPainelFase2(data) {
  atualizarPainelComKpis(data.kpis);

  const painelDados = getOrCreateSheet_(ERP_CONFIG.SHEETS.PAINEL_DADOS);
  painelDados.clear();

  escreverSerieFluxoNoPainelDados_(painelDados, data.serieFluxo);
  escreverTop10AtrasoNoPainelDados_(painelDados, data.top10Atraso);
  escreverResumoExecucaoNoPainelDados_(painelDados, data.resumoExecucao);

  gerarGraficoFluxoNoPainel_(data.serieFluxo.length);
  escreverTop10NoPainel_(data.top10Atraso);
}

function escreverSerieFluxoNoPainelDados_(sheet, serieFluxo) {
  const header = ['data', 'entradas_realizadas', 'saidas_realizadas', 'saldo_dia'];
  sheet.getRange(1, 1, 1, header.length).setValues([header]).setFontWeight('bold');

  if (!serieFluxo.length) return;

  const rows = serieFluxo.map(function (item) {
    return [item.data, item.entradas_realizadas, item.saidas_realizadas, item.saldo_dia];
  });

  sheet.getRange(2, 1, rows.length, header.length).setValues(rows);
}

function escreverTop10AtrasoNoPainelDados_(sheet, top10) {
  const startCol = 6;
  const header = ['cliente', 'qtd_titulos', 'valor_em_atraso'];
  sheet.getRange(1, startCol, 1, header.length).setValues([header]).setFontWeight('bold');

  if (!top10.length) return;

  const rows = top10.map(function (item) {
    return [item.cliente, item.qtd_titulos, item.valor_em_atraso];
  });
  sheet.getRange(2, startCol, rows.length, header.length).setValues(rows);
}

function escreverResumoExecucaoNoPainelDados_(sheet, resumo) {
  const startCol = 10;
  const rows = [
    ['metrica', 'valor'],
    ['total_titulos_receber', resumo.total_titulos_receber],
    ['total_titulos_pagar', resumo.total_titulos_pagar],
    ['total_registros_fluxo', resumo.total_registros_fluxo],
    ['atualizado_em', resumo.atualizado_em],
  ];

  sheet.getRange(1, startCol, rows.length, 2).setValues(rows);
  sheet.getRange(1, startCol, 1, 2).setFontWeight('bold');
}

function gerarGraficoFluxoNoPainel_(rowCount) {
  if (!rowCount) return;

  const painel = getOrCreateSheet_(ERP_CONFIG.SHEETS.PAINEL);
  const painelDados = getOrCreateSheet_(ERP_CONFIG.SHEETS.PAINEL_DADOS);

  const existingCharts = painel.getCharts();
  existingCharts.forEach(function (chart) {
    painel.removeChart(chart);
  });

  const range = painelDados.getRange(1, 1, rowCount + 1, 4);
  const chart = painel.newChart()
    .setChartType(Charts.ChartType.LINE)
    .addRange(range)
    .setPosition(8, 1, 0, 0)
    .setOption('title', 'Fluxo de Caixa Diário (30 dias)')
    .setOption('legend', { position: 'bottom' })
    .build();

  painel.insertChart(chart);
}

function escreverTop10NoPainel_(top10) {
  const painel = getOrCreateSheet_(ERP_CONFIG.SHEETS.PAINEL);
  const headerRow = 8;

  painel.getRange(headerRow, 7, 1, 3).setValues([['Top 10 clientes em atraso', 'Títulos', 'Valor em atraso']]);
  painel.getRange(headerRow, 7, 1, 3).setFontWeight('bold');

  if (!top10.length) {
    painel.getRange(headerRow + 1, 7).setValue('Sem registros de atraso no período.');
    return;
  }

  const rows = top10.map(function (item) {
    return [item.cliente, item.qtd_titulos, item.valor_em_atraso];
  });
  painel.getRange(headerRow + 1, 7, rows.length, 3).setValues(rows);
}

function writeSheetRows_(sheetName, headers, rows, mapper) {
  const sheet = getOrCreateSheet_(sheetName);
  sheet.clear();

  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.getRange(1, 1, 1, headers.length).setFontWeight('bold');

  if (!rows.length) {
    return;
  }

  const values = rows.map(mapper);
  sheet.getRange(2, 1, values.length, headers.length).setValues(values);
}

function getOrCreateSheet_(name) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  return ss.getSheetByName(name) || ss.insertSheet(name);
}

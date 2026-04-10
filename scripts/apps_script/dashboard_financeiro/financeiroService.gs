function sincronizarFinanceiroMvp() {
  const periodo = periodoPadraoUltimos30Dias();

  const receber = fetchAllPages('/financeiro/receber', periodo).map(normalizarReceber);
  const pagar = fetchAllPages('/financeiro/pagar', periodo).map(normalizarPagar);
  const fluxo = fetchAllPages('/financeiro/fluxo-caixa', periodo).map(normalizarFluxo);
  const kpisPayload = apiGet('/financeiro/kpis', periodo);
  const kpis = [normalizarKpis(kpisPayload)];

  escreverBaseReceber(receber);
  escreverBasePagar(pagar);
  escreverBaseFluxo(fluxo);
  escreverBaseKpis(kpis);
  atualizarPainelComKpis(kpis[0]);
}

function sincronizarFinanceiroFase2() {
  const periodo = periodoPadraoUltimos30Dias();

  const receber = fetchAllPages('/financeiro/receber', periodo).map(normalizarReceber);
  const pagar = fetchAllPages('/financeiro/pagar', periodo).map(normalizarPagar);
  const fluxo = fetchAllPages('/financeiro/fluxo-caixa', periodo).map(normalizarFluxo);
  const kpisPayload = apiGet('/financeiro/kpis', periodo);
  const kpis = normalizarKpis(kpisPayload);

  const top10Atraso = calcularTop10ClientesEmAtraso(receber, new Date());
  const serieFluxo = montarSerieFluxo30Dias(fluxo);
  const resumoExecucao = montarResumoExecucao(receber, pagar, fluxo);

  escreverBaseReceber(receber);
  escreverBasePagar(pagar);
  escreverBaseFluxo(fluxo);
  escreverBaseKpis([kpis]);
  atualizarPainelFase2({
    kpis: kpis,
    serieFluxo: serieFluxo,
    top10Atraso: top10Atraso,
    resumoExecucao: resumoExecucao,
  });
}

function periodoPadraoUltimos30Dias() {
  const hoje = new Date();
  const inicio = new Date(hoje.getTime() - 29 * 24 * 60 * 60 * 1000);

  return {
    data_inicio: formatDateISO(inicio),
    data_fim: formatDateISO(hoje),
  };
}

function normalizarReceber(item) {
  return {
    id_titulo: item.id_titulo || '',
    cliente: item.cliente || '',
    emissao: normalizeDate(item.emissao),
    vencimento: normalizeDate(item.vencimento),
    valor_original: toDecimal(item.valor_original),
    valor_aberto: toDecimal(item.valor_aberto),
    valor_pago: toDecimal(item.valor_pago),
    status: normalizeStatus(item.status),
    centro_custo: item.centro_custo || '',
  };
}

function normalizarPagar(item) {
  return {
    id_titulo: item.id_titulo || '',
    fornecedor: item.fornecedor || '',
    emissao: normalizeDate(item.emissao),
    vencimento: normalizeDate(item.vencimento),
    valor_original: toDecimal(item.valor_original),
    valor_aberto: toDecimal(item.valor_aberto),
    valor_pago: toDecimal(item.valor_pago),
    status: normalizeStatus(item.status),
    categoria_despesa: item.categoria_despesa || '',
  };
}

function normalizarFluxo(item) {
  return {
    data: normalizeDate(item.data),
    entradas_previstas: toDecimal(item.entradas_previstas),
    saidas_previstas: toDecimal(item.saidas_previstas),
    entradas_realizadas: toDecimal(item.entradas_realizadas),
    saidas_realizadas: toDecimal(item.saidas_realizadas),
    saldo_dia: toDecimal(item.saldo_dia),
    saldo_acumulado: toDecimal(item.saldo_acumulado),
  };
}

function normalizarKpis(item) {
  return {
    receita_mes: toDecimal(item.receita_mes),
    despesa_mes: toDecimal(item.despesa_mes),
    resultado_mes: toDecimal(item.resultado_mes),
    inadimplencia_valor: toDecimal(item.inadimplencia_valor),
    inadimplencia_percentual: toDecimal(item.inadimplencia_percentual),
    prazo_medio_recebimento: toDecimal(item.prazo_medio_recebimento),
    prazo_medio_pagamento: toDecimal(item.prazo_medio_pagamento),
    atualizado_em: formatDateTime(new Date()),
  };
}

function montarSerieFluxo30Dias(fluxoRows) {
  return fluxoRows
    .slice()
    .sort(function (a, b) {
      return a.data.localeCompare(b.data);
    })
    .map(function (item) {
      return {
        data: item.data,
        entradas_realizadas: item.entradas_realizadas,
        saidas_realizadas: item.saidas_realizadas,
        saldo_dia: item.saldo_dia,
      };
    });
}

function calcularTop10ClientesEmAtraso(receberRows, hoje) {
  const hojeIso = formatDateISO(hoje);
  const mapa = {};

  receberRows.forEach(function (item) {
    const emAtrasoPorStatus = item.status === 'vencido';
    const emAtrasoPorData = item.vencimento && item.vencimento < hojeIso && item.valor_aberto > 0;

    if (!emAtrasoPorStatus && !emAtrasoPorData) return;

    if (!mapa[item.cliente]) {
      mapa[item.cliente] = {
        cliente: item.cliente || 'Sem cliente',
        qtd_titulos: 0,
        valor_em_atraso: 0,
      };
    }

    mapa[item.cliente].qtd_titulos += 1;
    mapa[item.cliente].valor_em_atraso += item.valor_aberto;
  });

  return Object.keys(mapa)
    .map(function (key) { return mapa[key]; })
    .sort(function (a, b) {
      return b.valor_em_atraso - a.valor_em_atraso;
    })
    .slice(0, 10);
}

function montarResumoExecucao(receberRows, pagarRows, fluxoRows) {
  return {
    total_titulos_receber: receberRows.length,
    total_titulos_pagar: pagarRows.length,
    total_registros_fluxo: fluxoRows.length,
    atualizado_em: formatDateTime(new Date()),
  };
}

function normalizeDate(value) {
  if (!value) return '';
  const date = new Date(value);
  if (isNaN(date.getTime())) return '';
  return formatDateISO(date);
}

function formatDateISO(date) {
  return Utilities.formatDate(date, ERP_CONFIG.TIMEZONE, 'yyyy-MM-dd');
}

function formatDateTime(date) {
  return Utilities.formatDate(date, ERP_CONFIG.TIMEZONE, 'yyyy-MM-dd HH:mm:ss');
}

function normalizeStatus(status) {
  const current = String(status || '').trim().toLowerCase();
  if (!current) return 'desconhecido';

  const aliases = {
    aberto: 'aberto',
    parcial: 'parcial',
    pago: 'pago',
    vencido: 'vencido',
    overdue: 'vencido',
    paid: 'pago',
  };

  return aliases[current] || current;
}

function toDecimal(value) {
  const normalized = String(value || '0').replace(',', '.');
  const num = Number(normalized);
  return isNaN(num) ? 0 : num;
}

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
  const exec = sincronizarFinanceiroFase3({
    dias: 30,
    registrarExecucao: false,
    atualizarAlertas: false,
  });

  return exec;
}

function sincronizarFinanceiroFase3(options) {
  const opts = Object.assign({
    dias: 30,
    registrarExecucao: true,
    atualizarAlertas: true,
  }, options || {});

  const inicioExecucao = new Date();
  const periodo = periodoRelativoDias(opts.dias);
  let erro = null;

  try {
    const receber = fetchAllPages('/financeiro/receber', periodo).map(normalizarReceber);
    const pagar = fetchAllPages('/financeiro/pagar', periodo).map(normalizarPagar);
    const fluxo = fetchAllPages('/financeiro/fluxo-caixa', periodo).map(normalizarFluxo);
    const kpisPayload = apiGet('/financeiro/kpis', periodo);
    const kpis = normalizarKpis(kpisPayload);

    const top10Atraso = calcularTop10ClientesEmAtraso(receber, new Date());
    const serieFluxo = montarSerieFluxo30Dias(fluxo);
    const resumoExecucao = montarResumoExecucao(receber, pagar, fluxo, inicioExecucao);
    const agingReceber = calcularAgingReceber(receber, new Date());
    const desvioFluxo = calcularDesvioFluxo(serieFluxo);
    const alertas = construirAlertas(kpis, serieFluxo, desvioFluxo);

    escreverBaseReceber(receber);
    escreverBasePagar(pagar);
    escreverBaseFluxo(fluxo);
    escreverBaseKpis([kpis]);

    atualizarPainelFase2({
      kpis: kpis,
      serieFluxo: serieFluxo,
      top10Atraso: top10Atraso,
      resumoExecucao: resumoExecucao,
      agingReceber: agingReceber,
      desvioFluxo: desvioFluxo,
    });

    if (opts.atualizarAlertas) {
      escreverAlertas(alertas);
    }

    if (opts.registrarExecucao) {
      registrarExecucao(Object.assign({}, resumoExecucao, {
        status_execucao: 'sucesso',
        erro: '',
      }));
    }

    return {
      status: 'sucesso',
      periodo: periodo,
      resumoExecucao: resumoExecucao,
      alertas: alertas,
    };
  } catch (e) {
    erro = e;
    const resumoErro = {
      atualizado_em: formatDateTime(new Date()),
      inicio_execucao: formatDateTime(inicioExecucao),
      duracao_ms: new Date().getTime() - inicioExecucao.getTime(),
      total_titulos_receber: 0,
      total_titulos_pagar: 0,
      total_registros_fluxo: 0,
      status_execucao: 'erro',
      erro: String(e),
    };

    if (opts.registrarExecucao) {
      registrarExecucao(resumoErro);
    }

    throw erro;
  }
}

function periodoPadraoUltimos30Dias() {
  return periodoRelativoDias(30);
}

function periodoRelativoDias(dias) {
  const qtdDias = Math.max(1, Number(dias || 30));
  const hoje = new Date();
  const inicio = new Date(hoje.getTime() - (qtdDias - 1) * 24 * 60 * 60 * 1000);

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
        entradas_previstas: item.entradas_previstas,
        saidas_previstas: item.saidas_previstas,
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

    const chaveCliente = item.cliente || 'Sem cliente';

    if (!mapa[chaveCliente]) {
      mapa[chaveCliente] = {
        cliente: chaveCliente,
        qtd_titulos: 0,
        valor_em_atraso: 0,
      };
    }

    mapa[chaveCliente].qtd_titulos += 1;
    mapa[chaveCliente].valor_em_atraso += item.valor_aberto;
  });

  return Object.keys(mapa)
    .map(function (key) { return mapa[key]; })
    .sort(function (a, b) {
      return b.valor_em_atraso - a.valor_em_atraso;
    })
    .slice(0, 10);
}

function calcularAgingReceber(receberRows, hoje) {
  const hojeDt = new Date(formatDateISO(hoje));
  const buckets = {
    a_vencer: 0,
    atraso_1_30: 0,
    atraso_31_60: 0,
    atraso_61_90: 0,
    atraso_91_mais: 0,
  };

  receberRows.forEach(function (item) {
    if (item.valor_aberto <= 0 || !item.vencimento) return;

    const vencDt = new Date(item.vencimento);
    const diff = Math.floor((hojeDt.getTime() - vencDt.getTime()) / (24 * 60 * 60 * 1000));

    if (diff < 0) {
      buckets.a_vencer += item.valor_aberto;
    } else if (diff <= 30) {
      buckets.atraso_1_30 += item.valor_aberto;
    } else if (diff <= 60) {
      buckets.atraso_31_60 += item.valor_aberto;
    } else if (diff <= 90) {
      buckets.atraso_61_90 += item.valor_aberto;
    } else {
      buckets.atraso_91_mais += item.valor_aberto;
    }
  });

  return buckets;
}

function calcularDesvioFluxo(serieFluxo) {
  const acumulado = serieFluxo.reduce(function (acc, item) {
    const previsto = item.entradas_previstas - item.saidas_previstas;
    const realizado = item.entradas_realizadas - item.saidas_realizadas;

    acc.previsto += previsto;
    acc.realizado += realizado;
    return acc;
  }, { previsto: 0, realizado: 0 });

  const base = Math.abs(acumulado.previsto) || 1;
  const desvioPercentual = ((acumulado.realizado - acumulado.previsto) / base) * 100;

  return {
    previsto_liquido: acumulado.previsto,
    realizado_liquido: acumulado.realizado,
    desvio_percentual: desvioPercentual,
  };
}

function construirAlertas(kpis, serieFluxo, desvioFluxo) {
  const alertas = [];

  if (kpis.inadimplencia_percentual >= ERP_CONFIG.ALERT_THRESHOLDS.INADIMPLENCIA_PCT) {
    alertas.push({
      severidade: 'alta',
      codigo: 'inadimplencia_alta',
      mensagem: 'Inadimplência acima do limite configurado.',
      valor: kpis.inadimplencia_percentual,
    });
  }

  const diasSaldoNegativo = serieFluxo.filter(function (item) {
    return item.saldo_dia < ERP_CONFIG.ALERT_THRESHOLDS.SALDO_DIA_MINIMO;
  }).length;
  if (diasSaldoNegativo > 0) {
    alertas.push({
      severidade: 'media',
      codigo: 'saldo_negativo',
      mensagem: 'Existe saldo diário negativo no período.',
      valor: diasSaldoNegativo,
    });
  }

  if (Math.abs(desvioFluxo.desvio_percentual) >= ERP_CONFIG.ALERT_THRESHOLDS.DESVIO_CAIXA_PERCENTUAL) {
    alertas.push({
      severidade: 'media',
      codigo: 'desvio_fluxo',
      mensagem: 'Desvio previsto x realizado acima do limite.',
      valor: desvioFluxo.desvio_percentual,
    });
  }

  if (!alertas.length) {
    alertas.push({
      severidade: 'info',
      codigo: 'sem_alertas',
      mensagem: 'Sem alertas críticos no período.',
      valor: 0,
    });
  }

  return alertas;
}

function montarResumoExecucao(receberRows, pagarRows, fluxoRows, inicioExecucao) {
  const fim = new Date();
  return {
    total_titulos_receber: receberRows.length,
    total_titulos_pagar: pagarRows.length,
    total_registros_fluxo: fluxoRows.length,
    inicio_execucao: formatDateTime(inicioExecucao || fim),
    atualizado_em: formatDateTime(fim),
    duracao_ms: fim.getTime() - (inicioExecucao ? inicioExecucao.getTime() : fim.getTime()),
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

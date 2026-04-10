function sincronizarFinanceiroMvp() {
  const periodo = periodoPadraoUltimos30Dias();
  const resultado = executarSincronizacaoCore_(periodo, {
    registrarExecucao: false,
    atualizarAlertas: false,
    escreverEstado: false,
  });
  atualizarPainelComKpis(resultado.kpis);
}

function sincronizarFinanceiroFase2() {
  return sincronizarFinanceiroFase3({
    dias: 30,
    registrarExecucao: false,
    atualizarAlertas: false,
    escreverEstado: false,
  });
}

function sincronizarFinanceiroFase3(options) {
  const opts = Object.assign({
    dias: 30,
    registrarExecucao: true,
    atualizarAlertas: true,
    escreverEstado: false,
  }, options || {});

  const periodo = opts.periodo || periodoRelativoDias(opts.dias);
  return executarSincronizacaoCore_(periodo, opts);
}

function sincronizarFinanceiroFase4(options) {
  const opts = Object.assign({
    fullRefresh: false,
    diasFallback: ERP_CONFIG.FASE4.FULL_SYNC_DAYS,
    registrarExecucao: true,
    atualizarAlertas: true,
    persistirCheckpoint: true,
    overlapDays: ERP_CONFIG.FASE4.OVERLAP_DAYS,
  }, options || {});

  const lock = LockService.getScriptLock();
  const lockTimeoutMs = Number(ERP_CONFIG.FASE4.LOCK_TIMEOUT_MS || 25000);
  if (!lock.tryLock(lockTimeoutMs)) {
    throw new Error('Sincronização já em andamento. Tente novamente em instantes.');
  }

  try {
    const periodo = resolverPeriodoFase4_(opts);
    const resultado = executarSincronizacaoCore_(periodo, {
      registrarExecucao: opts.registrarExecucao,
      atualizarAlertas: opts.atualizarAlertas,
      escreverEstado: true,
    });

    if (opts.persistirCheckpoint) {
      salvarCheckpointFase4_(resultado.resumoExecucao.atualizado_em, 'sucesso');
    }

    return Object.assign({}, resultado, {
      modo: 'fase4',
      checkpoint: carregarCheckpointFase4_(),
    });
  } catch (error) {
    salvarCheckpointFase4_(formatDateISO(new Date()), 'erro: ' + String(error));
    throw error;
  } finally {
    lock.releaseLock();
  }
}

function executarSincronizacaoCore_(periodo, opts) {
  const options = Object.assign({
    registrarExecucao: true,
    atualizarAlertas: true,
    escreverEstado: false,
  }, opts || {});

  const inicioExecucao = new Date();

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
    const conciliacao = calcularConciliacaoFinanceira(kpis, receber, pagar, fluxo);
    const alertas = construirAlertas(kpis, serieFluxo, desvioFluxo, conciliacao);

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
      conciliacao: conciliacao,
    });

    if (options.atualizarAlertas) {
      escreverAlertas(alertas);
    }

    if (options.escreverEstado) {
      escreverEstadoSincronizacao({
        periodo_inicio: periodo.data_inicio,
        periodo_fim: periodo.data_fim,
        status: 'sucesso',
        atualizado_em: resumoExecucao.atualizado_em,
        checkpoint: carregarCheckpointFase4_(),
      });
    }

    if (options.registrarExecucao) {
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
      kpis: kpis,
      conciliacao: conciliacao,
    };
  } catch (e) {
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

    if (options.registrarExecucao) {
      registrarExecucao(resumoErro);
    }

    if (options.escreverEstado) {
      escreverEstadoSincronizacao({
        periodo_inicio: periodo.data_inicio,
        periodo_fim: periodo.data_fim,
        status: 'erro',
        atualizado_em: resumoErro.atualizado_em,
        checkpoint: carregarCheckpointFase4_(),
      });
    }

    throw e;
  }
}

function resolverPeriodoFase4_(opts) {
  if (opts.fullRefresh) {
    return periodoRelativoDias(opts.diasFallback);
  }

  const checkpoint = carregarCheckpointFase4_();
  if (!checkpoint) {
    return periodoRelativoDias(opts.diasFallback);
  }

  const fim = new Date();
  const inicio = new Date(checkpoint + 'T00:00:00');
  const overlap = Math.max(0, Number(opts.overlapDays || 0));
  inicio.setDate(inicio.getDate() - overlap);

  return {
    data_inicio: formatDateISO(inicio),
    data_fim: formatDateISO(fim),
  };
}

function carregarCheckpointFase4_() {
  const key = ERP_CONFIG.FASE4.SYNC_STATE_PROPERTY_KEY;
  return PropertiesService.getScriptProperties().getProperty(key);
}

function salvarCheckpointFase4_(dataIso, status) {
  const props = PropertiesService.getScriptProperties();
  props.setProperty(ERP_CONFIG.FASE4.SYNC_STATE_PROPERTY_KEY, String(dataIso || ''));
  props.setProperty(ERP_CONFIG.FASE4.LAST_STATUS_PROPERTY_KEY, String(status || ''));
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
      mapa[chaveCliente] = { cliente: chaveCliente, qtd_titulos: 0, valor_em_atraso: 0 };
    }

    mapa[chaveCliente].qtd_titulos += 1;
    mapa[chaveCliente].valor_em_atraso += item.valor_aberto;
  });

  return Object.keys(mapa)
    .map(function (key) { return mapa[key]; })
    .sort(function (a, b) { return b.valor_em_atraso - a.valor_em_atraso; })
    .slice(0, 10);
}

function calcularAgingReceber(receberRows, hoje) {
  const hojeDt = new Date(formatDateISO(hoje));
  const buckets = { a_vencer: 0, atraso_1_30: 0, atraso_31_60: 0, atraso_61_90: 0, atraso_91_mais: 0 };

  receberRows.forEach(function (item) {
    if (item.valor_aberto <= 0 || !item.vencimento) return;

    const vencDt = new Date(item.vencimento);
    const diff = Math.floor((hojeDt.getTime() - vencDt.getTime()) / (24 * 60 * 60 * 1000));

    if (diff < 0) buckets.a_vencer += item.valor_aberto;
    else if (diff <= 30) buckets.atraso_1_30 += item.valor_aberto;
    else if (diff <= 60) buckets.atraso_31_60 += item.valor_aberto;
    else if (diff <= 90) buckets.atraso_61_90 += item.valor_aberto;
    else buckets.atraso_91_mais += item.valor_aberto;
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
  return {
    previsto_liquido: acumulado.previsto,
    realizado_liquido: acumulado.realizado,
    desvio_percentual: ((acumulado.realizado - acumulado.previsto) / base) * 100,
  };
}

function calcularConciliacaoFinanceira(kpis, receberRows, pagarRows, fluxoRows) {
  const abertoReceber = receberRows.reduce(function (acc, item) { return acc + item.valor_aberto; }, 0);
  const abertoPagar = pagarRows.reduce(function (acc, item) { return acc + item.valor_aberto; }, 0);
  const saldoFluxo = fluxoRows.reduce(function (acc, item) { return acc + item.saldo_dia; }, 0);

  return {
    aberto_receber: abertoReceber,
    aberto_pagar: abertoPagar,
    diferenca_resultado_kpi: kpis.resultado_mes - (kpis.receita_mes - kpis.despesa_mes),
    saldo_fluxo_agregado: saldoFluxo,
  };
}

function construirAlertas(kpis, serieFluxo, desvioFluxo, conciliacao) {
  const alertas = [];

  if (kpis.inadimplencia_percentual >= ERP_CONFIG.ALERT_THRESHOLDS.INADIMPLENCIA_PCT) {
    alertas.push({ severidade: 'alta', codigo: 'inadimplencia_alta', mensagem: 'Inadimplência acima do limite configurado.', valor: kpis.inadimplencia_percentual });
  }

  const diasSaldoNegativo = serieFluxo.filter(function (item) {
    return item.saldo_dia < ERP_CONFIG.ALERT_THRESHOLDS.SALDO_DIA_MINIMO;
  }).length;
  if (diasSaldoNegativo > 0) {
    alertas.push({ severidade: 'media', codigo: 'saldo_negativo', mensagem: 'Existe saldo diário negativo no período.', valor: diasSaldoNegativo });
  }

  if (Math.abs(desvioFluxo.desvio_percentual) >= ERP_CONFIG.ALERT_THRESHOLDS.DESVIO_CAIXA_PERCENTUAL) {
    alertas.push({ severidade: 'media', codigo: 'desvio_fluxo', mensagem: 'Desvio previsto x realizado acima do limite.', valor: desvioFluxo.desvio_percentual });
  }

  if (Math.abs(conciliacao.diferenca_resultado_kpi) > 0.01) {
    alertas.push({ severidade: 'media', codigo: 'conciliacao_kpi', mensagem: 'Diferença entre KPI de resultado e cálculo receita-despesa.', valor: conciliacao.diferenca_resultado_kpi });
  }

  if (!alertas.length) {
    alertas.push({ severidade: 'info', codigo: 'sem_alertas', mensagem: 'Sem alertas críticos no período.', valor: 0 });
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

  const aliases = { aberto: 'aberto', parcial: 'parcial', pago: 'pago', vencido: 'vencido', overdue: 'vencido', paid: 'pago' };
  return aliases[current] || current;
}

function toDecimal(value) {
  const normalized = String(value || '0').replace(',', '.');
  const num = Number(normalized);
  return isNaN(num) ? 0 : num;
}

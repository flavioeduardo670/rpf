# Dashboard Financeiro — ERP → API → Google Apps Script → Google Sheets

Este pacote cobre três fases evolutivas.

## Fase 1

1. Contas a Receber
2. Contas a Pagar
3. Fluxo de Caixa (realizado e previsto)
4. Resumo mensal (KPIs)

## Fase 2

1. Gráfico automático de fluxo de caixa diário na aba `painel`.
2. Tabela de Top 10 clientes em atraso na aba `painel`.
3. Aba auxiliar `painel_dados` para datasets do painel.

## Fase 3

1. **Orquestração robusta** com `sincronizarFinanceiroFase3(options)`.
2. **Retry HTTP** para erros transitórios (429/5xx).
3. **Alertas operacionais** (`painel_alertas`) com limiares configuráveis.
4. **Log de execução** (`painel_execucao`) com duração e status.
5. **Novas análises**: aging de contas a receber e desvio previsto x realizado de fluxo.

## Estrutura

- `apiClient.gs`: autenticação, retry, paginação e chamadas HTTP para a API do ERP.
- `financeiroService.gs`: normalização, agregações e orquestrações das fases 1/2/3.
- `dashboardWriter.gs`: gravação de abas base, renderização do painel e persistência de alertas/log.

## Endpoints esperados

- `GET /financeiro/receber`
- `GET /financeiro/pagar`
- `GET /financeiro/fluxo-caixa`
- `GET /financeiro/kpis`

Parâmetros comuns:

- `data_inicio` (YYYY-MM-DD)
- `data_fim` (YYYY-MM-DD)
- `page`
- `page_size`

## Como usar

1. Crie um projeto no Google Apps Script vinculado à planilha.
2. Copie os três arquivos `.gs` para o projeto.
3. Ajuste `ERP_CONFIG` (URL, token, timezone, limiares e nomes de abas).
4. Execute `sincronizarFinanceiroFase3()`.
5. (Opcional) Para janela customizada: `sincronizarFinanceiroFase3({ dias: 45 })`.
6. (Opcional) Crie gatilho diário para atualização automática.

## Abas criadas/atualizadas

- `base_receber`
- `base_pagar`
- `base_fluxo`
- `base_kpis`
- `painel`
- `painel_dados`
- `painel_alertas`
- `painel_execucao`

## Observações

- O script usa paginação para evitar timeout no Apps Script.
- Datas são normalizadas para `YYYY-MM-DD`.
- Valores monetários são convertidos para número decimal com ponto.
- O painel é reescrito a cada execução para manter consistência dos dados.

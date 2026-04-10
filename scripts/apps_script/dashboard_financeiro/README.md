# Dashboard Financeiro — ERP → API → Google Apps Script → Google Sheets

Este pacote cobre:

## Fase 1

1. Contas a Receber
2. Contas a Pagar
3. Fluxo de Caixa (realizado e previsto)
4. Resumo mensal (KPIs)

## Fase 2

1. Gráfico automático de fluxo de caixa diário (30 dias) na aba `painel`.
2. Tabela de Top 10 clientes em atraso na aba `painel`.
3. Abas auxiliares para dados do painel e telemetria da sincronização.
4. Orquestração única por `sincronizarFinanceiroFase2()`.

## Estrutura

- `apiClient.gs`: autenticação, paginação e chamadas HTTP para a API do ERP.
- `financeiroService.gs`: normalização dos dados e regras de agregação de fase 1 e fase 2.
- `dashboardWriter.gs`: gravação de abas base + construção/atualização do painel.

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
3. Ajuste `ERP_CONFIG` (URL, token, timezone e nomes de abas).
4. Execute `sincronizarFinanceiroFase2()` para usar o pacote completo.
5. (Opcional) Crie gatilho diário para atualização automática.

## Abas criadas/atualizadas

- `base_receber`
- `base_pagar`
- `base_fluxo`
- `base_kpis`
- `painel`
- `painel_dados`
- `painel_execucao` (reservada para evolução)

## Observações

- O script usa paginação para evitar timeout no Apps Script.
- Datas são normalizadas para `YYYY-MM-DD`.
- Valores monetários são convertidos para número decimal com ponto.
- O gráfico e a tabela de Top 10 são reconstruídos a cada sincronização.

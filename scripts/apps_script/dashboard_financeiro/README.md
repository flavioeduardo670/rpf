# Dashboard Financeiro — ERP → API → Google Apps Script → Google Sheets

Este pacote cobre quatro fases evolutivas.

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

1. Orquestração robusta com `sincronizarFinanceiroFase3(options)`.
2. Retry HTTP para erros transitórios (429/5xx).
3. Alertas operacionais (`painel_alertas`) com limiares configuráveis.
4. Log de execução (`painel_execucao`) com duração e status.
5. Análises de aging e desvio previsto x realizado.

## Fase 4

1. **Sincronização incremental** com checkpoint via Script Properties.
2. **Controle de concorrência** com `LockService` para evitar dupla execução.
3. **Modo full refresh** opcional (`fullRefresh: true`) com fallback de dias configurável.
4. **Estado de sync** em aba dedicada (`painel_estado_sync`).
5. **Conciliação financeira adicional** (`aberto_receber`, `aberto_pagar`, diferença de KPI e saldo agregado de fluxo).
6. Suporte a token em Script Properties (`ERP_BEARER_TOKEN`) para não deixar segredo no código.

## Estrutura

- `apiClient.gs`: autenticação, retry, paginação e chamadas HTTP para a API do ERP.
- `financeiroService.gs`: normalização, agregações e orquestrações das fases 1/2/3/4.
- `dashboardWriter.gs`: gravação de abas base, renderização do painel e persistência operacional.
- `../rpf_system_api.gs`: cliente Apps Script para o **sistema RPF (Django)** via login + exportação CSV autenticada.

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
3. Ajuste `ERP_CONFIG` (URL, token, timezone, limiares e abas).
4. (Recomendado) configure o token em Script Properties com a chave `ERP_BEARER_TOKEN`.
5. Execute `sincronizarFinanceiroFase4()`.

### Consumir API/exports do próprio sistema RPF (Django)

Se você quiser consumir os dados do sistema RPF diretamente (sem endpoints `/api/financeiro/*`), use o script:

- `scripts/apps_script/rpf_system_api.gs`

Esse script:

1. Faz login em `/login/` (captura CSRF + cookie de sessão).
2. Baixa CSVs autenticados:
   - `/moradores/exportar/`
   - `/financeiro/exportar/?mes=YYYY-MM`
   - `/compras/exportar/`
   - `/almoxarifado/exportar/`
   - `/almoxarifado/consumo/exportar/`
3. Escreve tudo em abas da planilha.

Funções principais:

- `sincronizarRpfCsvs()` → sincroniza todos os CSVs.
- `sincronizarFinanceiroPorMesRpf('2026-04')` → sincroniza só o financeiro por mês.

Exemplos:

- Incremental padrão: `sincronizarFinanceiroFase4()`
- Full refresh: `sincronizarFinanceiroFase4({ fullRefresh: true })`
- Janela fallback customizada: `sincronizarFinanceiroFase4({ diasFallback: 90 })`

## Abas criadas/atualizadas

- `base_receber`
- `base_pagar`
- `base_fluxo`
- `base_kpis`
- `painel`
- `painel_dados`
- `painel_alertas`
- `painel_execucao`
- `painel_estado_sync`

## Observações

- O script usa paginação para evitar timeout no Apps Script.
- Datas são normalizadas para `YYYY-MM-DD`.
- Valores monetários são convertidos para número decimal com ponto.
- A fase 4 persiste checkpoint de sucesso para acelerar execuções agendadas.

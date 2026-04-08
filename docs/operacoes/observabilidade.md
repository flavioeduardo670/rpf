# Base de observabilidade operacional

## Logs estruturados

- Todos os logs passam pelo formatter `rpf.logging.JsonFormatter`.
- Campos padrão emitidos: `timestamp`, `level`, `logger`, `message`, `module`, `function`, `line` e `event` (quando informado).
- Níveis por domínio configuráveis por variáveis de ambiente:
  - `DJANGO_LOG_LEVEL`
  - `CORE_VIEWS_LOG_LEVEL`
  - `CORE_SERVICES_LOG_LEVEL`
  - `ROOT_LOG_LEVEL`

## Healthcheck

- Endpoint: `GET /healthz`
- Resposta esperada:
  - `200` quando aplicação e banco estiverem operacionais.
  - `503` quando o banco falhar.
- Payload inclui `status` e `checks` (`app`, `database`).

## Captura de exceções não tratadas (Sentry)

Variáveis:

- `SENTRY_DSN`: habilita integração quando preenchida.
- `SENTRY_ENVIRONMENT`: ambiente lógico (ex.: `development`, `staging`, `production`).
- `SENTRY_TRACES_SAMPLE_RATE`: amostragem de traces (0.0 a 1.0).
- `SENTRY_PROFILES_SAMPLE_RATE`: amostragem de perfis (0.0 a 1.0).

## Painéis e alertas mínimos

### 1) Erros HTTP 5xx

- **Métrica**: taxa de respostas `status >= 500`.
- **Alerta sugerido**: disparar quando taxa de 5xx > 2% por 5 minutos.

### 2) Latência da aplicação

- **Métrica**: p95 de tempo de resposta por endpoint (priorizar `/`, `/comprar_rocks`, `/healthz`).
- **Alerta sugerido**: p95 > 1500ms por 10 minutos.

### 3) Indisponibilidade de healthcheck

- **Métrica**: sucesso/falha de `GET /healthz` e tempo de resposta.
- **Alerta sugerido**: 3 falhas consecutivas ou `status != 200` por 2 minutos.

### 4) Falhas no fluxo PIX

Eventos instrumentados (campo `event`):

- `pix.purchase.start`
- `pix.purchase.validation_error`
- `pix.purchase.order_created`
- `pix.purchase.charge_created`
- `pix.charge.configuration_error`
- `pix.charge.gateway_error`
- `pix.status.gateway_error`

Alertas recomendados:

- Taxa de `pix.charge.gateway_error` > 5 em 10 minutos.
- Taxa de `pix.purchase.validation_error` acima da média histórica.
- Crescimento de pedidos com `status_gateway=desconhecido` por mais de 15 minutos.

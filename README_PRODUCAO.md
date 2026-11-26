# Operação segura em produção

## Variáveis obrigatórias

- `DJANGO_DEBUG=False`
- `DJANGO_SECRET_KEY` com valor forte
- `DJANGO_ALLOWED_HOSTS` (obrigatório em produção)
- `CSRF_TRUSTED_ORIGINS` com origens `https://`

## Variáveis recomendadas

- `RENDER_EXTERNAL_HOSTNAME` para incluir automaticamente domínio público Render nas origens CSRF
- `SECURE_HSTS_SECONDS`:
  - início: `86400`
  - após validação completa HTTPS + subdomínios: `31536000`
- `SECURE_HSTS_PRELOAD=True` somente quando domínio/subdomínios estiverem prontos para preload
- `MERCADOPAGO_WEBHOOK_SECRET`: **obrigatória se o PIX estiver em uso** — sem ela o webhook de pagamento é recusado (HTTP 400) para impedir confirmações falsas.

## Pagamento do aluguel (boleto PIX) e recibo por email

Para o sistema reconhecer sozinho o pagamento do boleto e mandar o recibo:

1. `MERCADOPAGO_ACCESS_TOKEN` — sem ele o boleto sai com um PIX "local" (chave da
   casa), que **não** é reconhecido automaticamente. Use o **Access Token de produção
   da conta real que recebe o aluguel** (com chave PIX cadastrada no Mercado Pago).
   O token de produção de um *usuário de teste* é recusado com
   `401 Unauthorized use of live credentials`; a tela Financeiro → Aluguel mostra
   esse motivo quando acontece.
2. `MERCADOPAGO_NOTIFICATION_URL=https://<seu-dominio>/financeiro/pix/webhook/` e
   `MERCADOPAGO_WEBHOOK_SECRET` (mesma URL/segredo cadastrados no painel do Mercado Pago).
3. Email do recibo. **No plano gratuito do Render o SMTP de saída (portas 25, 465 e
   587) é bloqueado**: a conexão fica pendurada e não funciona. Use a API HTTPS do
   Brevo (grátis até 300 emails/dia):
   - `BREVO_API_KEY` (Brevo → SMTP & API → API Keys);
   - `DJANGO_DEFAULT_FROM_EMAIL=República RPF <email-verificado-no-brevo>` (o remetente
     precisa estar verificado em Brevo → Senders).
   Em plano pago (ou fora do Render), o SMTP comum também serve: `DJANGO_EMAIL_HOST`,
   `DJANGO_EMAIL_PORT`, `DJANGO_EMAIL_HOST_USER`, `DJANGO_EMAIL_HOST_PASSWORD`,
   `DJANGO_EMAIL_USE_TLS=True`. Qualquer envio tem timeout de `DJANGO_EMAIL_TIMEOUT`
   (10 s) e a tela do financeiro tenta no máximo 3 recibos por visita.
4. Email de cada morador preenchido no cadastro.
5. Garantia para webhook perdido / email que falhou — rodar a cada 15–30 min (Cron Job do Render):

   ```bash
   python manage.py verificar_pagamentos_aluguel
   ```

Pagamento que não passou pelo Mercado Pago (PIX local, dinheiro, transferência):
botão **Confirmar pagamento** na coluna Status de Financeiro → Aluguel. Ele quita a
mensalidade, cancela o PIX pendente no Mercado Pago e envia o recibo.

Sem SMTP o recibo não sai por email; ele continua disponível em PDF pelo botão
"Gerar boleto de aluguel" do mês já pago.

O QR do boleto vale até o dia 10 do mês (ou 3 dias a partir da emissão, se já passou);
ao regerar o boleto, um QR vencido é trocado e o anterior é cancelado no Mercado Pago.

## Vários clientes (organizações) no mesmo sistema

Cada organização recebe na **própria conta do Mercado Pago**:

1. **Antes do primeiro deploy com isto**, defina `CREDENCIAIS_CHAVE` (a chave que
   cifra os tokens no banco). Gere uma vez e guarde em lugar seguro:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`.
   Sem ela a chave sai da `DJANGO_SECRET_KEY`, e trocar a SECRET_KEY apagaria os tokens.
2. A migração `0077` copia `MERCADOPAGO_ACCESS_TOKEN` e `MERCADOPAGO_WEBHOOK_SECRET`
   do servidor para a **primeira organização** (a Portão). Depois disso, troque o
   token pelo **Admin → Organizações** (campos "Token do Mercado Pago" e "Assinatura
   secreta"); as variáveis do servidor só valem enquanto houver um cliente só.
3. `MERCADOPAGO_NOTIFICATION_URL` continua sendo a base
   (`https://<seu-dominio>/financeiro/pix/webhook/`); cada cobrança é criada com o
   endereço do cliente (`.../webhook/<slug>/`). No painel do Mercado Pago **de cada
   cliente**, cadastre o webhook que aparece na tela dele no Admin. O endereço antigo,
   sem slug, continua valendo para a primeira organização.
4. Remetente dos recibos: com mais de um cliente, sai o nome da organização com o
   endereço de `DJANGO_DEFAULT_FROM_EMAIL`; as respostas vão para o "Email de contato"
   da organização.
5. `verificar_pagamentos_aluguel` e `notificar_pagamento_aluguel` percorrem todos os
   clientes. `importar_nfe_receita` e `importar_notas_email` usam o certificado e a
   caixa de email do servidor, que são da **primeira organização**.

## Deploy (ordem dos comandos)

```bash
pip install -r requirements.txt
python manage.py collectstatic --noinput
python manage.py migrate --noinput
# só então reiniciar/publicar a aplicação (ex.: gunicorn rpf.wsgi)
```

## Comportamento de segurança com `DJANGO_DEBUG=False`

- `SECURE_SSL_REDIRECT=True`
- `SESSION_COOKIE_SECURE=True`
- `CSRF_COOKIE_SECURE=True`
- `SECURE_HSTS_INCLUDE_SUBDOMAINS=True`
- `SECURE_PROXY_SSL_HEADER=('HTTP_X_FORWARDED_PROTO', 'https')`
- `SESSION_COOKIE_HTTPONLY=True`

---

# Runbook de storage (estáticos + mídia)

## Estratégia de estáticos

Definida por `DJANGO_STATIC_STRATEGY`:

- `whitenoise`: app serve estáticos compilados (`collectstatic`) com hash.
- `cdn`: `STATIC_URL` aponta para `DJANGO_STATIC_CDN_URL`.

> Em ambos os casos, `MEDIA` segue configuração própria e separada.

## Estratégia de mídia

Definida por `DJANGO_MEDIA_BACKEND`:

- `local`: grava em disco local (`MEDIA_ROOT`).
- `s3`: usa backend `storages.backends.s3.S3Storage`.

### Variáveis para backend `s3`

Obrigatórias:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_STORAGE_BUCKET_NAME`

Comuns:

- `AWS_S3_REGION_NAME`
- `AWS_S3_ENDPOINT_URL`
- `AWS_MEDIA_LOCATION` (default `media`)
- `AWS_MEDIA_URL` (opcional)
- `AWS_S3_CUSTOM_DOMAIN` (opcional)
- `AWS_MEDIA_CACHE_CONTROL` (default `max-age=86400`)

## Política de backup/retention/versionamento

Aplicar no bucket de mídia:

1. **Versionamento habilitado**.
2. **Retention**:
   - versões não-correntes retidas por 90 dias;
   - delete marker cleanup conforme política da nuvem;
   - abort multipart incompleto após 7 dias.
3. **Backup/DR**:
   - replicação cross-region ou backup periódico externo;
   - restauração testada trimestralmente;
   - trilha de auditoria para operações de delete.

## Recuperação de mídia (incidente)

1. Congelar uploads no app (maintenance mode ou regra WAF).
2. Identificar janela de incidente e prefixo afetado no bucket.
3. Restaurar versão anterior dos objetos (versionamento).
4. Validar amostra funcional (perfil com foto, downloads, admin).
5. Reabrir escrita.
6. Registrar pós-mortem com causa, impacto e ações corretivas.

## Migração de mídia local para bucket

### Pré-migração

1. Inventariar local:

```bash
python3 scripts/storage/audit_local_media.py > media-inventory.json
```

2. Validar total de arquivos e volume.
3. Definir janela de corte para evitar divergência de escrita.

### Execução

```bash
aws s3 sync media/ s3://$AWS_STORAGE_BUCKET_NAME/$AWS_MEDIA_LOCATION/ --exact-timestamps
```

### Pós-migração

1. Conferir contagem de objetos vs inventário.
2. Validar abertura de arquivos críticos no app.
3. Ativar `DJANGO_MEDIA_BACKEND=s3` no deploy.
4. Manter fallback local por janela definida (ex.: 7 dias).

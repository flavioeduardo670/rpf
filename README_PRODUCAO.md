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

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

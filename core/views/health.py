import logging

from django.db import connections
from django.http import JsonResponse
from django.views.decorators.http import require_GET

logger = logging.getLogger('core.views.health')


@require_GET
def healthz(request):
    checks = {
        'app': 'ok',
        'database': 'ok',
    }
    status_code = 200

    try:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
    except Exception:
        checks['database'] = 'erro'
        status_code = 503
        logger.exception('Healthcheck com falha de banco', extra={'event': 'healthcheck.database_error'})

    if status_code == 200:
        logger.info('Healthcheck OK', extra={'event': 'healthcheck.ok'})

    return JsonResponse(
        {
            'status': 'ok' if status_code == 200 else 'degradado',
            'checks': checks,
        },
        status=status_code,
    )

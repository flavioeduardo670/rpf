import json
import logging
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
        }

        request_id = getattr(record, 'request_id', None)
        if request_id:
            payload['request_id'] = request_id

        event = getattr(record, 'event', None)
        if event:
            payload['event'] = event

        for key, value in record.__dict__.items():
            if key.startswith('_'):
                continue
            if key in {
                'name', 'msg', 'args', 'levelname', 'levelno', 'pathname', 'filename',
                'module', 'exc_info', 'exc_text', 'stack_info', 'lineno', 'funcName',
                'created', 'msecs', 'relativeCreated', 'thread', 'threadName',
                'processName', 'process', 'message',
            }:
                continue
            if key not in payload:
                payload[key] = value

        if record.exc_info:
            payload['exc_info'] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False, default=str)

import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import PlainTextResponse

REQUEST_COUNT = {}
REQUEST_LATENCY = {}
ERROR_COUNT = {}

class PrometheusMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        method = request.method
        path = request.url.path

        if path == "/metrics":
            return await call_next(request)

        start = time.time()
        try:
            response = await call_next(request)
            status = response.status_code
        except Exception:
            status = 500
            raise
        finally:
            duration = time.time() - start
            key = f'{method}_{path}_{status}'
            REQUEST_COUNT[key] = REQUEST_COUNT.get(key, 0) + 1

            lat_key = f'{method}_{path}'
            if lat_key not in REQUEST_LATENCY:
                REQUEST_LATENCY[lat_key] = []
            REQUEST_LATENCY[lat_key].append(duration)

            if status >= 400:
                err_key = f'{method}_{path}_{status}'
                ERROR_COUNT[err_key] = ERROR_COUNT.get(err_key, 0) + 1

        return response

def metrics_endpoint(request: Request):
    lines = []
    lines.append("# HELP http_requests_total Total HTTP requests")
    lines.append("# TYPE http_requests_total counter")
    for key, count in REQUEST_COUNT.items():
        parts = key.split("_", 2)
        method = parts[0]
        rest = "_".join(parts[1:])
        path_status = rest.rsplit("_", 1)
        path = path_status[0] if len(path_status) > 1 else rest
        status = path_status[1] if len(path_status) > 1 else "200"
        lines.append(f'http_requests_total{{method="{method}",path="{path}",status="{status}"}} {count}')

    lines.append("# HELP http_request_duration_seconds HTTP request latency")
    lines.append("# TYPE http_request_duration_seconds histogram")
    for key, durations in REQUEST_LATENCY.items():
        parts = key.split("_", 1)
        method = parts[0]
        path = parts[1] if len(parts) > 1 else "/"
        lines.append(f'http_request_duration_seconds_sum{{method="{method}",path="{path}"}} {sum(durations):.6f}')
        lines.append(f'http_request_duration_seconds_count{{method="{method}",path="{path}"}} {len(durations)}')

    return PlainTextResponse("\n".join(lines) + "\n", media_type="text/plain")

import ipaddress
import uuid
from django.conf import settings
from django.http import HttpResponseForbidden, JsonResponse

def client_ip(request):
    address = request.META.get('REMOTE_ADDR', '127.0.0.1')
    try:
        peer = ipaddress.ip_address(address)
        if any(peer in network for network in settings.TRUSTED_PROXY_NETWORKS):
            # Caddy must overwrite this single-value header, never pass a visitor's value through.
            value = request.META.get('HTTP_X_REAL_IP', address)
            return str(ipaddress.ip_address(value))
        return str(peer)
    except ValueError:
        return '0.0.0.0'

class RequestMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.request_id = uuid.uuid4().hex
        if request.path.startswith('/tongjian/admin/'):
            address = ipaddress.ip_address(client_ip(request))
            if not any(address in network for network in settings.ADMIN_NETWORKS):
                response = HttpResponseForbidden('管理入口不可从此网络访问。')
                response['Cache-Control'] = 'private, no-store'
                response['X-Request-ID'] = request.request_id
                return response
        response = self.get_response(request)
        if request.path.startswith('/tongjian/api/') and response.status_code >= 400 and 'application/json' not in response.get('Content-Type', ''):
            response = JsonResponse({'error': {'code': 'not_found' if response.status_code == 404 else 'request_failed',
                                      'message': '未找到请求内容。' if response.status_code == 404 else '请求暂无法完成。'},
                                     'request_id': request.request_id}, status=response.status_code)
        response['X-Request-ID'] = request.request_id
        private = ('/tongjian/api/', '/tongjian/account/', '/tongjian/article/', '/tongjian/checkout/', '/tongjian/admin/')
        if request.path.startswith(private):
            response['Cache-Control'] = 'private, no-store'
            response['X-Robots-Tag'] = 'noindex, nofollow'
        return response

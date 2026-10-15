import json
from functools import wraps
from urllib.parse import urlsplit, unquote
import posixpath

from django.http import JsonResponse

class Problem(Exception):
    def __init__(self, code, message, status=400):
        self.code, self.message, self.status = code, message, status

def endpoint(view):
    @wraps(view)
    def wrapped(request, *args, **kwargs):
        try:
            return view(request, *args, **kwargs)
        except Problem as exc:
            return JsonResponse({'error': {'code': exc.code, 'message': exc.message},
                                 'request_id': request.request_id}, status=exc.status)
    return wrapped

def body(request):
    if len(request.body) > 16384:
        raise Problem('invalid_request', '请求过长。')
    try:
        data = json.loads(request.body)
        if not isinstance(data, dict):
            raise ValueError()
        return data
    except (ValueError, UnicodeDecodeError):
        raise Problem('invalid_request', '请求格式不正确。')

def user_required(request):
    if not request.user.is_authenticated:
        raise Problem('login_required', '请先登录。', 401)

def safe_next(value):
    if not isinstance(value, (str, type(None))):
        return '/tongjian/account/purchases/'
    value = value or '/tongjian/account/purchases/'
    parts = urlsplit(value)
    decoded = unquote(parts.path)
    if (parts.scheme or parts.netloc or len(value) > 2048 or not posixpath.normpath(decoded).startswith('/tongjian/')
            or '\\' in decoded or any(ord(c) < 32 for c in unquote(value))):
        return '/tongjian/account/purchases/'
    return value

def csrf_failure(request, reason=''):
    if not request.path.startswith('/tongjian/api/'):
        from django.shortcuts import render
        return render(request, 'csrf_failure.html', status=403)
    return JsonResponse({'error': {'code': 'csrf_failed', 'message': '页面验证已失效，请刷新后重试。'},
                         'request_id': getattr(request, 'request_id', '')}, status=403)

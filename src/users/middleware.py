"""Attach the signed-in user so model saves can record staff changes."""

from users.audit import reset_audit_user, set_audit_user


class StaffAuditMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        token = set_audit_user(getattr(request, "user", None))
        try:
            return self.get_response(request)
        finally:
            reset_audit_user(token)

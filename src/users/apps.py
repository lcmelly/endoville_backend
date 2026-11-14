from django.apps import AppConfig


class UsersConfig(AppConfig):
    name = 'users'

    def ready(self):
        from rest_framework.views import APIView

        from users.audit import set_audit_user

        if getattr(APIView, "_staff_audit_wrapped", False):
            return
        original_initial = APIView.initial

        def initial(view, request, *args, **kwargs):
            original_initial(view, request, *args, **kwargs)
            set_audit_user(getattr(request, "user", None))

        APIView.initial = initial
        APIView._staff_audit_wrapped = True

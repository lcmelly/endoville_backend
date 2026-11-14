"""
URL configuration for users app
"""
from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    path('register/', views.register_view, name='register'),
    path('activate/', views.activate_account_view, name='activate'),
    path('send-otp/', views.send_otp_view, name='send-otp'),
    path('request-login-otp/', views.request_login_otp_view, name='request-login-otp'),
    path('login/', views.login_view, name='login'),
    path('google-login/', views.google_login_view, name='google-login'),
    path('me/', views.me_view, name='me'),
    path('is-staff/', views.is_staff_view, name='is-staff'),
    path('staff/', views.staff_users_view, name='staff-users'),
    path('staff/<int:user_id>/', views.staff_user_detail_view, name='staff-user'),
    path('staff-changes/', views.staff_change_log_view, name='staff-changes'),
    path('customers/', views.staff_customers_view, name='customers'),
]


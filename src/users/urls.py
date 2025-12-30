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
    path('login/', views.login_view, name='login'),
    path('google-login/', views.google_login_view, name='google-login'),
]


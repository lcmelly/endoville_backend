"""
URL configuration for orders app.
"""

from django.urls import include, path
from rest_framework.routers import DefaultRouter

from . import views
from .views import (
    CartViewSet,
    OrderPaymentViewSet,
    OrderViewSet,
    PaymentCredentialsViewSet,
    ShipmentViewSet,
    StaffBackgroundTaskViewSet,
    StaffOrderPaymentViewSet,
    StaffOrderRefundViewSet,
    StaffShipmentEventViewSet,
    StaffShipmentViewSet,
    WarehouseViewSet,
)

app_name = "orders"

router = DefaultRouter()
router.register(r"orders", OrderViewSet, basename="order")
router.register(r"cart", CartViewSet, basename="cart")
router.register(r"shipments", ShipmentViewSet, basename="shipment")
router.register(r"payments", OrderPaymentViewSet, basename="payment")

# Staff-only management endpoints (no admin UI needed)
router.register(r"payment-credentials", PaymentCredentialsViewSet, basename="payment-credentials")
router.register(r"staff/payments", StaffOrderPaymentViewSet, basename="staff-payment")
router.register(r"staff/refunds", StaffOrderRefundViewSet, basename="staff-refund")
router.register(r"staff/warehouses", WarehouseViewSet, basename="staff-warehouse")
router.register(r"staff/shipments", StaffShipmentViewSet, basename="staff-shipment")
router.register(r"staff/shipment-events", StaffShipmentEventViewSet, basename="staff-shipment-event")
router.register(
    r"staff/background-tasks",
    StaffBackgroundTaskViewSet,
    basename="staff-background-task",
)

urlpatterns = [
    path("payments/stripe/webhook/", views.stripe_webhook_view, name="stripe-webhook"),
    path("payments/intasend/test/", views.intasend_test_connection, name="intasend-test"),
    path("shipping-rates/", views.ShippingRatesView.as_view(), name="shipping-rates"),
    path("shipping-rates/quote/", views.ShippingQuoteView.as_view(), name="shipping-quote"),
    path("", include(router.urls)),
]

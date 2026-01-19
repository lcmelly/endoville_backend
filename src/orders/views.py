"""
API views for orders app.
"""

from django.conf import settings
from rest_framework import mixins, status, viewsets
from rest_framework.response import Response

from .models import Order, OrderPayment, PaymentCredentials, PaymentProvider, Shipment, ShipmentEvent
from .permissions import IsStaffOnly, IsStaffOrOwner
from .serializers import (
    CreateOrderPaymentSerializer,
    CreateOrderSerializer,
    OrderPaymentSerializer,
    OrderSerializer,
    PaymentCredentialsSerializer,
    StaffOrderPaymentUpdateSerializer,
    StaffShipmentEventCreateSerializer,
    StaffShipmentUpdateSerializer,
    ShipmentSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    """
    Users can create and view their own orders.
    Staff can view/manage all orders.
    """

    permission_classes = [IsStaffOrOwner]

    def get_queryset(self):
        qs = (
            Order.objects.select_related("user", "shipping_address")
            .prefetch_related("items", "items__variant", "items__product", "shipment", "shipment__events")
            .order_by("-created_at")
        )
        if self.request.user.is_staff:
            return qs
        return qs.filter(user=self.request.user)

    def get_serializer_class(self):
        if self.action == "create":
            return CreateOrderSerializer
        return OrderSerializer

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        return Response(OrderSerializer(order).data, status=status.HTTP_201_CREATED)


class ShipmentViewSet(mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Read-only access for users to track shipments for their orders.
    Staff can list all.
    """

    permission_classes = [IsStaffOrOwner]
    serializer_class = ShipmentSerializer

    def get_queryset(self):
        qs = Shipment.objects.select_related("order", "order__user").prefetch_related("events").order_by("-created_at")
        if self.request.user.is_staff:
            return qs
        return qs.filter(order__user=self.request.user)


class OrderPaymentViewSet(mixins.CreateModelMixin, mixins.RetrieveModelMixin, mixins.ListModelMixin, viewsets.GenericViewSet):
    """
    Users can create payments for their own orders and view payment status/links.
    Staff can view all payments.
    """

    permission_classes = [IsStaffOrOwner]
    serializer_class = OrderPaymentSerializer

    def get_queryset(self):
        qs = OrderPayment.objects.select_related("order", "order__user").filter(is_deleted=False).order_by("-created_at")
        if self.request.user.is_staff:
            return qs
        return qs.filter(order__user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = CreateOrderPaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        order_id = request.data.get("order")
        if not order_id:
            return Response({"order": ["This field is required."]}, status=status.HTTP_400_BAD_REQUEST)

        try:
            order = Order.objects.select_related("user", "shipping_address").get(id=order_id)
        except Order.DoesNotExist:
            return Response({"order": ["Order not found."]}, status=status.HTTP_404_NOT_FOUND)

        # Enforce ownership (auth required by permission)
        if not request.user.is_staff and order.user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        # Block creating payments for fully paid orders
        if order.recalculate_is_fully_paid():
            return Response(
                {"detail": "Order is already fully paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        provider = serializer.validated_data["provider"]
        method = serializer.validated_data["method"]
        amount = serializer.validated_data.get("amount") or order.total
        currency = serializer.validated_data.get("currency") or "KES"

        payment = OrderPayment.objects.create(
            order=order,
            provider=provider,
            amount=amount,
            currency=currency,
        )

        # Kick off provider workflow
        try:
            if provider in [PaymentProvider.CASH, PaymentProvider.OTHER]:
                # Manual payments are recorded and later confirmed by staff via staff/payments endpoints.
                return Response(OrderPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

            if provider == PaymentProvider.INTASEND:
                from .payments.intasend import IntaSendAPI

                client = IntaSendAPI()
                if method == "stk":
                    client.initiate_stk_push(
                        payment,
                        phone_number=serializer.validated_data.get("phone_number") or None,
                        email=serializer.validated_data.get("email") or None,
                    )
                else:
                    client.create_payment_link(payment)
            elif provider == PaymentProvider.STRIPE:
                from .payments.stripe import StripeAPI

                client = StripeAPI()
                success_url = getattr(settings, "STRIPE_SUCCESS_URL", "https://yourdomain.com/payment/success/")
                cancel_url = getattr(settings, "STRIPE_CANCEL_URL", "https://yourdomain.com/payment/cancel/")
                client.create_checkout_session(payment, success_url=success_url, cancel_url=cancel_url)
            else:
                return Response(
                    {"detail": "Provider not supported yet."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        except Exception as e:
            # Payment record exists; return error to client
            return Response(
                {"detail": str(e), "payment": OrderPaymentSerializer(payment).data},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(OrderPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)


class PaymentCredentialsViewSet(viewsets.ModelViewSet):
    """
    Staff-only CRUD for global payment credentials.
    """

    permission_classes = [IsStaffOnly]
    queryset = PaymentCredentials.objects.all().order_by("-created_at")
    serializer_class = PaymentCredentialsSerializer


class StaffOrderPaymentViewSet(viewsets.ModelViewSet):
    """
    Staff-only CRUD to manually update payment status/provider fields.
    """

    permission_classes = [IsStaffOnly]
    serializer_class = StaffOrderPaymentUpdateSerializer

    def get_queryset(self):
        qs = OrderPayment.objects.select_related("order").order_by("-created_at")
        include_deleted = str(self.request.query_params.get("include_deleted", "")).lower() in ["1", "true", "yes"]
        if include_deleted:
            return qs
        return qs.filter(is_deleted=False)

    def perform_destroy(self, instance):
        # Soft delete and record who deleted it
        instance.soft_delete(user=self.request.user)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data.get("order")
        if order and order.recalculate_is_fully_paid():
            return Response({"detail": "Order is already fully paid."}, status=status.HTTP_400_BAD_REQUEST)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class StaffShipmentViewSet(viewsets.ModelViewSet):
    """
    Staff-only CRUD for shipments (status + tracking info).
    """

    permission_classes = [IsStaffOnly]
    queryset = Shipment.objects.select_related("order", "order__user").order_by("-created_at")
    serializer_class = StaffShipmentUpdateSerializer


class StaffShipmentEventViewSet(viewsets.ModelViewSet):
    """
    Staff-only CRUD for shipment events (timeline updates users see).
    """

    permission_classes = [IsStaffOnly]
    queryset = ShipmentEvent.objects.select_related("shipment", "shipment__order").order_by("-occurred_at")
    serializer_class = StaffShipmentEventCreateSerializer


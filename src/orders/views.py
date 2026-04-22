"""
API views for orders app.
"""

from background_task.models import CompletedTask, Task
from django.conf import settings
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response

from .currency_utils import order_total_in_currency
from .models import Cart, CartItem, Order, OrderPayment, OrderStatus, PaymentCredentials, PaymentProvider, PaymentStatus, Shipment, ShipmentEvent
from .permissions import IsStaffOnly, IsStaffOrOwner
from .serializers import (
    BackgroundTaskSerializer,
    CartSerializer,
    CompletedBackgroundTaskSerializer,
    CreateOrderPaymentSerializer,
    CreateOrderSerializer,
    OrderPaymentSerializer,
    OrderSerializer,
    PaymentCredentialsSerializer,
    SyncCartSerializer,
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

    def update(self, request, *args, **kwargs):
        return self._update_order(request, partial=False, **kwargs)

    def partial_update(self, request, *args, **kwargs):
        return self._update_order(request, partial=True, **kwargs)

    def _update_order(self, request, partial=False, **kwargs):
        order = self.get_object()

        if not request.user.is_staff:
            status_value = request.data.get("status")
            if set(request.data.keys()) != {"status"} or status_value != OrderStatus.CANCELLED:
                return Response(
                    {"detail": "You can only cancel your own unpaid orders."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if order.recalculate_is_fully_paid():
                return Response(
                    {"detail": "Only unpaid orders can be cancelled."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(order, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)


class CartViewSet(viewsets.GenericViewSet):
    """
    User cart APIs for frontend synchronization.
    """

    permission_classes = [IsStaffOrOwner]
    serializer_class = CartSerializer

    def _get_or_create_cart(self, user):
        cart, _ = Cart.objects.get_or_create(user=user)
        return cart

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        cart = self._get_or_create_cart(request.user)
        cart = Cart.objects.prefetch_related(
            "items__product", "items__variant", "items__variant__product", "items__variant__options__attribute"
        ).get(pk=cart.pk)
        return Response(CartSerializer(cart, context={"request": request}).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["put", "post"], url_path="sync")
    @transaction.atomic
    def sync(self, request):
        serializer = SyncCartSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        cart = self._get_or_create_cart(request.user)

        CartItem.objects.filter(cart=cart).delete()
        for item in serializer.validated_data["items"]:
            CartItem.objects.create(
                cart=cart,
                product=item.get("product"),
                variant=item.get("variant"),
                quantity=item["quantity"],
            )

        cart.mark_active()
        cart = Cart.objects.prefetch_related(
            "items__product", "items__variant", "items__variant__product", "items__variant__options__attribute"
        ).get(pk=cart.pk)
        return Response(CartSerializer(cart, context={"request": request}).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=["delete"], url_path="clear")
    @transaction.atomic
    def clear(self, request):
        cart = self._get_or_create_cart(request.user)
        cart.clear_items()
        cart = Cart.objects.prefetch_related(
            "items__product", "items__variant", "items__variant__product", "items__variant__options__attribute"
        ).get(pk=cart.pk)
        return Response(CartSerializer(cart, context={"request": request}).data, status=status.HTTP_200_OK)


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

    @action(detail=True, methods=["post"], url_path="check-status")
    def check_status(self, request, pk=None):
        """
        Refresh payment status from the provider when still pending/processing.
        If payment is already completed, failed, or cancelled, returns stored status without calling the provider.
        """
        payment = self.get_object()
        payment.refresh_from_db()
        result = {
            "is_complete": payment.status == PaymentStatus.COMPLETED,
            "status": payment.status,
            "provider_state": payment.provider_state or "",
        }
        # Only call third-party API when status is still pending or processing
        if payment.status not in (
            PaymentStatus.COMPLETED,
            PaymentStatus.FAILED,
            PaymentStatus.CANCELLED,
        ):
            if payment.provider == PaymentProvider.INTASEND and (
                payment.provider_invoice_id or payment.provider_payment_id
            ):
                try:
                    from .payments.intasend import IntaSendAPI

                    client = IntaSendAPI()
                    check_result = client.check_payment_status(payment)
                    payment.refresh_from_db()
                    result["is_complete"] = payment.status == PaymentStatus.COMPLETED
                    result["status"] = payment.status
                    result["provider_state"] = payment.provider_state or ""
                    result["success"] = check_result.get("success", False)
                    if not check_result.get("success"):
                        result["error"] = check_result.get("error")
                except Exception as e:
                    result["success"] = False
                    result["error"] = str(e)
            else:
                result["success"] = True
        else:
            result["success"] = True
        return Response(
            {"payment": OrderPaymentSerializer(payment).data, "status_check": result},
            status=status.HTTP_200_OK,
        )

    def create(self, request, *args, **kwargs):
        serializer = CreateOrderPaymentSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)

        order = serializer.validated_data["order"]
        order = Order.objects.select_related("user", "shipping_address").get(pk=order.pk)

        # Enforce ownership (auth required by permission)
        if not request.user.is_staff and order.user_id != request.user.id:
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        # Block creating payments for fully paid orders
        if order.recalculate_is_fully_paid():
            return Response(
                {"detail": "Order is already fully paid."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Payment is linked to the order from the request; amount = order total (converted to payment currency)
        provider = serializer.validated_data["provider"]
        method = serializer.validated_data["method"]
        currency = serializer.validated_data.get("currency") or "USD"
        amount = serializer.validated_data.get("amount")
        if amount is None:
            amount = order_total_in_currency(order.total, currency)

        # IntaSend: sync all related payments from stored provider_state and API; block if order fully paid
        if provider == PaymentProvider.INTASEND:
            intasend_payments = OrderPayment.objects.filter(
                order=order,
                provider=PaymentProvider.INTASEND,
                is_deleted=False,
            )
            intasend_client = None
            for payment in intasend_payments:
                state = (payment.provider_state or "").upper()
                if state in ("COMPLETE", "COMPLETED", "PAID", "SETTLED") and payment.status not in (
                    PaymentStatus.COMPLETED,
                    PaymentStatus.FAILED,
                    PaymentStatus.CANCELLED,
                ):
                    payment.status = PaymentStatus.COMPLETED
                    payment.save(update_fields=["status", "updated_at"])
                elif payment.provider_invoice_id or payment.provider_payment_id:
                    try:
                        if intasend_client is None:
                            from .payments.intasend import IntaSendAPI
                            intasend_client = IntaSendAPI()
                        intasend_client.check_payment_status(payment)
                    except Exception:
                        pass
            if order.recalculate_is_fully_paid():
                return Response(
                    {"detail": "Order is already fully paid."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        # IntaSend link only: if order already has a pending IntaSend payment with a link, return it
        if provider == PaymentProvider.INTASEND and method == "link":
            existing = (
                OrderPayment.objects.filter(
                    order=order,
                    provider=PaymentProvider.INTASEND,
                    is_deleted=False,
                    status__in=[PaymentStatus.PENDING, PaymentStatus.PROCESSING],
                )
                .exclude(checkout_url="")
                .order_by("-created_at")
                .first()
            )
            if existing:
                # Email will be sent when payment is completed (see OrderPayment.save())
                return Response(OrderPaymentSerializer(existing).data, status=status.HTTP_201_CREATED)

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
                # Email will be sent when payment is completed (see OrderPayment.save())
                return Response(OrderPaymentSerializer(payment).data, status=status.HTTP_201_CREATED)

            if provider == PaymentProvider.INTASEND:
                from .payments.intasend import IntaSendAPI

                client = IntaSendAPI()
                if method == "stk":
                    phone = (
                        serializer.validated_data.get("phone_number")
                        or getattr(order.shipping_address, "phone", None)
                        or ""
                    )
                    result = client.initiate_stk_push(
                        payment,
                        phone_number=phone,
                        email=serializer.validated_data.get("email") or None,
                        narrative=serializer.validated_data.get("narrative") or None,
                    )
                    if not result.get("success"):
                        return Response(
                            {"detail": result.get("error", "STK push failed."), "payment": OrderPaymentSerializer(payment).data},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
                else:
                    result = client.create_payment_link(
                        payment,
                        phone_number=serializer.validated_data.get("phone_number") or None,
                        email=serializer.validated_data.get("email") or None,
                    )
                    if not result.get("success"):
                        return Response(
                            {"detail": result.get("error", "Failed to create payment link."), "payment": OrderPaymentSerializer(payment).data},
                            status=status.HTTP_400_BAD_REQUEST,
                        )
            elif provider == PaymentProvider.STRIPE:
                from .payments.stripe import StripeAPI

                # Stripe creds loaded from PaymentCredentials (DB) only
                client = StripeAPI()
                success_url = (
                    (serializer.validated_data.get("success_url") or "").strip()
                    or getattr(settings, "STRIPE_SUCCESS_URL", "https://yourdomain.com/payment/success/")
                )
                cancel_url = (
                    (serializer.validated_data.get("cancel_url") or "").strip()
                    or getattr(settings, "STRIPE_CANCEL_URL", "https://yourdomain.com/payment/cancel/")
                )
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

        # Email will be sent when payment is completed (see OrderPayment.save())
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


class StaffBackgroundTaskViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """
    Staff-only read access to django-background-tasks queue (`Task`) and recent archive (`CompletedTask`).

    This shows **when the worker will run** reminder processing (and repeats), not ZeptoMail’s own
    outbound queue. Cart emails send when `run_abandoned_cart_reminders_task` runs successfully.
    """

    permission_classes = [IsStaffOnly]
    serializer_class = BackgroundTaskSerializer

    def get_queryset(self):
        qs = Task.objects.all()
        tname = self.request.query_params.get("task_name", "").strip()
        if tname:
            qs = qs.filter(task_name__icontains=tname)
        queue = self.request.query_params.get("queue", "").strip()
        if queue:
            qs = qs.filter(queue=queue)
        return qs.order_by("run_at", "id")

    def list(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())
        try:
            lim = int(request.query_params.get("limit", "200"))
        except ValueError:
            lim = 200
        lim = max(1, min(lim, 500))
        serializer = self.get_serializer(queryset[:lim], many=True)
        return Response(serializer.data)

    @action(detail=False, methods=["get"], url_path="completed")
    def completed(self, request):
        qs = CompletedTask.objects.all().order_by("-run_at")
        tname = request.query_params.get("task_name", "").strip()
        if tname:
            qs = qs.filter(task_name__icontains=tname)
        queue = request.query_params.get("queue", "").strip()
        if queue:
            qs = qs.filter(queue=queue)
        try:
            lim = int(request.query_params.get("limit", "100"))
        except ValueError:
            lim = 100
        lim = max(1, min(lim, 500))
        return Response(CompletedBackgroundTaskSerializer(qs[:lim], many=True).data)


@csrf_exempt
@require_http_methods(["POST"])
def stripe_webhook_view(request):
    """
    Stripe webhook: verify signature and on checkout.session.completed mark the payment as completed.
    Configure STRIPE_WEBHOOK_SECRET in settings (e.g. from env) and point Stripe to this URL.
    """
    payload = request.body
    sig = request.headers.get("Stripe-Signature", "")
    webhook_secret = getattr(settings, "STRIPE_WEBHOOK_SECRET", None) or ""
    if not webhook_secret:
        return HttpResponse("Webhook secret not configured.", status=400)
    try:
        import stripe as stripe_lib
        event = stripe_lib.Webhook.construct_event(payload, sig, webhook_secret)
    except ValueError as e:
        return HttpResponse(f"Invalid payload: {e}", status=400)
    except Exception as e:
        return HttpResponse(f"Invalid signature: {e}", status=400)
    if event["type"] == "checkout.session.completed":
        session_id = event.get("data", {}).get("object", {}).get("id")
        if session_id:
            from .payments.stripe import complete_payment_for_session
            complete_payment_for_session(session_id)
    return HttpResponse(status=200)


@api_view(["GET"])
@permission_classes([IsStaffOnly])
def intasend_test_connection(request):
    """
    Test IntaSend API connection using stored credentials.
    Staff only. Returns 200 with status if service initializes, 400 with error otherwise.
    """
    try:
        from .payments.intasend import IntaSendAPI

        IntaSendAPI(user=request.user)
        return Response(
            {"status": "ok", "message": "IntaSend service initialized successfully"},
            status=status.HTTP_200_OK,
        )
    except ValueError as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_400_BAD_REQUEST,
        )
    except ImportError as e:
        return Response(
            {"status": "error", "message": str(e)},
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )


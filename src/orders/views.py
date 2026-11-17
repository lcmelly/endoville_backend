"""
API views for orders app.
"""

from background_task.models import CompletedTask, Task
from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import AllowAny, SAFE_METHODS
from rest_framework.throttling import SimpleRateThrottle
from rest_framework.views import APIView
from rest_framework.decorators import action, api_view, permission_classes
from rest_framework.response import Response
from rest_framework.serializers import ValidationError as SerializerValidationError

from .currency_utils import order_total_in_currency, snapshot_usd_rate
from .customer_messages import CustomerMessageReadSerializer, CustomerMessageSerializer, MESSAGE_MAX_LENGTH
from .models import (
    CLOSED_PAYMENT_STATUSES,
    Cart,
    CustomerMessage,
    CartItem,
    Order,
    OrderItem,
    OrderPayment,
    OrderRefund,
    OrderStatus,
    PaymentCredentials,
    PaymentProvider,
    PaymentStatus,
    Shipment,
    ShipmentEvent,
    Warehouse,
)
from users.roles import has_staff_role

from .permissions import IsAdmin, IsManagerOrAdmin, IsStaffOnly, IsStaffOrOwner, StaffRolePermission


def payment_create_rejection(order):
    """
    A new payment is refused when the order is cancelled or the money already covers it.
    """
    if order.status == OrderStatus.CANCELLED:
        return Response(
            {"detail": "Cannot record a payment for a cancelled order."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    if order.is_fully_paid:
        return Response(
            {"detail": "Order is already fully paid."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return None
from .serializers import (
    BackgroundTaskSerializer,
    CartSerializer,
    CompletedBackgroundTaskSerializer,
    CreateOrderPaymentSerializer,
    CreateOrderSerializer,
    OrderPaymentSerializer,
    OrderRefundSerializer,
    OrderSerializer,
    ReplaceOrderItemSerializer,
    PaymentCredentialsSerializer,
    ShippingQuoteSerializer,
    ShippingRatesSerializer,
    shipping_rates_payload,
    SyncCartSerializer,
    StaffOrderPaymentUpdateSerializer,
    StaffShipmentEventCreateSerializer,
    StaffShipmentUpdateSerializer,
    ShipmentSerializer,
    WarehouseUpdateSerializer,
)


class OrderViewSet(viewsets.ModelViewSet):
    lookup_field = "public_id"
    lookup_url_kwarg = "pk"
    """
    Users can create and view their own orders.
    Staff can view/manage all orders.
    """

    permission_classes = [IsStaffOrOwner]

    def get_queryset(self):
        qs = (
            Order.objects.select_related("user", "shipping_address")
            .prefetch_related(
                "items",
                "items__variant",
                "items__product",
                "items__replacement",
                "shipment",
                "shipment__events",
                "refunds",
            )
            .order_by("-created_at")
        )
        if has_staff_role(self.request.user, "Orders", "Shipping"):
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

        if not has_staff_role(request.user, "Orders"):
            status_value = request.data.get("status")
            if set(request.data.keys()) != {"status"} or status_value != OrderStatus.CANCELLED:
                return Response(
                    {"detail": "You can only cancel your own unpaid orders."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if order.is_fully_paid:
                return Response(
                    {"detail": "Only unpaid orders can be cancelled."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        serializer = self.get_serializer(order, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        self.perform_update(serializer)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def _staff_line_change(self, request, item_id, action):
        if not has_staff_role(request.user, "Orders"):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)
        order = self.get_object()
        try:
            item = order.items.get(pk=item_id)
        except OrderItem.DoesNotExist:
            return Response({"detail": "Order line not found."}, status=status.HTTP_404_NOT_FOUND)
        try:
            action(order, item)
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            return Response({"detail": message}, status=status.HTTP_400_BAD_REQUEST)
        cache = getattr(order, "_prefetched_objects_cache", None)
        if cache is not None:
            cache.pop("items", None)
            cache.pop("refunds", None)
        order.refresh_from_db()
        return Response(OrderSerializer(order, context={"request": request}).data, status=status.HTTP_200_OK)

    def _line_note(self, request):
        note = request.data.get("note", "") if hasattr(request.data, "get") else ""
        return note if isinstance(note, str) else ""

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>[^/.]+)/confirm")
    def confirm_item(self, request, pk=None, item_id=None):
        note = self._line_note(request)
        return self._staff_line_change(
            request,
            item_id,
            lambda order, item: order.confirm_line(item, request.user, note=note),
        )

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>[^/.]+)/unavailable")
    def unavailable_item(self, request, pk=None, item_id=None):
        note = self._line_note(request)
        return self._staff_line_change(
            request,
            item_id,
            lambda order, item: order.mark_line_unavailable(item, request.user, note=note),
        )

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>[^/.]+)/remove")
    def remove_item(self, request, pk=None, item_id=None):
        note = self._line_note(request)
        return self._staff_line_change(
            request,
            item_id,
            lambda order, item: order.mark_line_unavailable(item, request.user, note=note),
        )

    @action(detail=True, methods=["post"], url_path=r"items/(?P<item_id>[^/.]+)/replace")
    def replace_item(self, request, pk=None, item_id=None):
        serializer = ReplaceOrderItemSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        product = serializer.validated_data.get("product")
        variant = serializer.validated_data.get("variant")

        def _replace(order, item):
            quantity = serializer.validated_data.get("quantity", item.quantity)
            order.replace_line(item, product, variant, quantity, request.user)

        return self._staff_line_change(request, item_id, _replace)


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
        country = serializer.validated_data.get("country") or request.query_params.get("country") or ""
        return Response(
            CartSerializer(cart, context={"request": request, "country": country}).data,
            status=status.HTTP_200_OK,
        )

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
        if has_staff_role(self.request.user, "Orders", "Shipping"):
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
        if has_staff_role(self.request.user, "Orders"):
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
        if payment.status not in CLOSED_PAYMENT_STATUSES:
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
            elif payment.provider == PaymentProvider.STRIPE and payment.provider_payment_id:
                try:
                    from .payments.stripe import StripeAPI

                    client = StripeAPI()
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
        if order.user_id != request.user.id and not has_staff_role(request.user, "Orders"):
            return Response({"detail": "Not allowed."}, status=status.HTTP_403_FORBIDDEN)

        from .payments.stripe import sync_open_stripe_payments

        stripe_error = sync_open_stripe_payments(order)
        if stripe_error:
            return Response({"detail": stripe_error}, status=status.HTTP_400_BAD_REQUEST)
        order.refresh_from_db(fields=["status", "total", "is_fully_paid"])

        rejection = payment_create_rejection(order)
        if rejection is not None:
            return rejection

        # Payment is linked to the order from the request; amount = order total (converted to payment currency)
        provider = serializer.validated_data["provider"]
        method = serializer.validated_data["method"]
        currency = serializer.validated_data.get("currency") or "USD"
        amount = serializer.validated_data.get("amount")
        from .payments.stripe_rates import ensure_stripe_rates_fresh

        ensure_stripe_rates_fresh()
        if amount is None:
            amount = order_total_in_currency(order.total, currency)
        fx_rate = snapshot_usd_rate(currency)

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
                if state in ("COMPLETE", "COMPLETED", "PAID", "SETTLED") and payment.status not in CLOSED_PAYMENT_STATUSES:
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
            order.refresh_from_db(fields=["status", "total", "is_fully_paid"])
            if order.is_fully_paid:
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
            usd_rate=fx_rate,
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

    permission_classes = [StaffRolePermission("Orders")]
    queryset = PaymentCredentials.objects.all().order_by("-created_at")
    serializer_class = PaymentCredentialsSerializer


class StaffOrderPaymentViewSet(
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.ListModelMixin,
    viewsets.GenericViewSet,
):
    """
    Staff can record and read payments. Payments are not edited or deleted.
    Returning money is a refund.
    """

    permission_classes = [StaffRolePermission("Orders")]
    serializer_class = StaffOrderPaymentUpdateSerializer
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        qs = OrderPayment.objects.select_related("order").order_by("-created_at")
        include_deleted = str(self.request.query_params.get("include_deleted", "")).lower() in ["1", "true", "yes"]
        if include_deleted:
            return qs
        return qs.filter(is_deleted=False)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        order = serializer.validated_data.get("order")
        if order is not None:
            from .payments.stripe import sync_open_stripe_payments

            stripe_error = sync_open_stripe_payments(order)
            if stripe_error:
                return Response({"detail": stripe_error}, status=status.HTTP_400_BAD_REQUEST)
            order.refresh_from_db(fields=["status", "total", "is_fully_paid"])
            rejection = payment_create_rejection(order)
            if rejection is not None:
                return rejection
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class StaffOrderRefundViewSet(viewsets.ModelViewSet):
    """
    Staff record a refund for a completed payment on a cancelled order.
    """

    permission_classes = [StaffRolePermission("Orders")]
    serializer_class = OrderRefundSerializer
    http_method_names = ["get", "post", "patch", "head", "options"]
    queryset = OrderRefund.objects.select_related("order", "payment", "initiated_by").order_by("-created_at")


class WarehouseViewSet(
    mixins.CreateModelMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read receiving warehouses, or set and change an address.
    Creates and updates are limited to managers and Django admins.
    """

    queryset = Warehouse.objects.all().order_by("name")
    serializer_class = WarehouseUpdateSerializer
    http_method_names = ["get", "post", "put", "patch", "head", "options"]

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [IsStaffOnly()]
        return [IsManagerOrAdmin()]


class StaffShipmentViewSet(viewsets.ModelViewSet):
    """
    Staff-only CRUD for shipments (status + tracking info).
    """

    permission_classes = [StaffRolePermission("Shipping")]
    queryset = Shipment.objects.select_related("order", "order__user").order_by("-created_at")
    serializer_class = StaffShipmentUpdateSerializer


class StaffShipmentEventViewSet(viewsets.ModelViewSet):
    """
    Staff-only CRUD for shipment events (timeline updates users see).
    """

    permission_classes = [StaffRolePermission("Shipping")]
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
@permission_classes([StaffRolePermission("Orders")])
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


class CustomerMessageThrottle(SimpleRateThrottle):
    """Five message submissions per hour for one IP address."""

    scope = "customer_messages"

    def get_cache_key(self, request, view):
        if request.method != "POST":
            return None
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


class CustomerMessageView(APIView):
    """
    Anyone can send a message.
    A submission needs an email or a phone number, a short message, and a captcha token.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def get_throttles(self):
        if self.request.method == "POST":
            return [CustomerMessageThrottle()]
        return []

    def get(self, request):
        return Response(
            {
                "message_max_length": MESSAGE_MAX_LENGTH,
                "captcha_site_key": getattr(settings, "CUSTOMER_MESSAGE_CAPTCHA_SITE_KEY", ""),
                "captcha_provider": "turnstile",
            }
        )

    def post(self, request):
        serializer = CustomerMessageSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        try:
            message = serializer.save()
        except SerializerValidationError as exc:
            return Response(exc.detail, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            CustomerMessageReadSerializer(message).data,
            status=status.HTTP_201_CREATED,
        )


class StaffCustomerMessageViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Staff read customer messages. Shoppers cannot list them."""

    permission_classes = [IsStaffOnly]
    serializer_class = CustomerMessageReadSerializer
    queryset = CustomerMessage.objects.select_related("order").order_by("-created_at")


class ShippingRatesView(APIView):
    """
    Read the shipping table, or replace it.
    Anyone can read. Only an admin can change the country rates.
    """

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAdmin()]

    def get(self, request):
        return Response(shipping_rates_payload())

    def put(self, request):
        serializer = ShippingRatesSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(shipping_rates_payload())


class ShippingQuoteView(APIView):
    """Quote a shipping fee from a destination country and the items' product weights."""

    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ShippingQuoteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.quote())


"""
Insert sandbox catalog, users, blog content, carts, and orders.

Safe to run more than once: rows are matched on stable emails, slugs, and
order notes, and existing rows are left in place.

    python manage.py seed_sandbox
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from blogs.models import Author, Category as BlogCategory, Comment, Post, Subcategory as BlogSubcategory
from orders.currency_utils import order_total_in_currency
from orders.models import (
    Cart,
    CartItem,
    LineAvailability,
    Order,
    OrderItem,
    OrderPayment,
    OrderStatus,
    PaymentProvider,
    PaymentStatus,
    Shipment,
    ShipmentEvent,
    ShippingAddress,
    ShippingStatus,
)
from products.models import (
    Brand,
    Category,
    Currency,
    Product,
    ProductReview,
    ProductVariant,
    Subcategory,
    VariationAttribute,
    VariationOption,
)

User = get_user_model()

SANDBOX_PASSWORD = "sandbox-pass-123"


class Command(BaseCommand):
    help = "Insert sandbox users, catalog, blog posts, carts, and orders."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            default=SANDBOX_PASSWORD,
            help="Password assigned to sandbox users that do not exist yet.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        password = options["password"]
        self.stdout.write("Seeding sandbox data")

        self._currencies()
        brands = self._brands()
        subcategories = self._catalog_taxonomy()
        products = self._products(brands, subcategories)
        variants = self._variants(products)
        users = self._users(password)
        post = self._blog(products["vitamin_d3"], users["ada"])
        self._cart(users["bola"], products["serum"], products["magnesium"])
        self._orders(users, products, variants)
        self._review(users["ada"], products["omega"])

        self.stdout.write(self.style.SUCCESS("Sandbox data is ready."))
        self.stdout.write(f"Password for newly created users: {password}")
        self.stdout.write("Staff (admin): sandbox.staff@endovillehealth.com")
        self.stdout.write("Customers: ada.sandbox@example.com, bola.sandbox@example.com, chidi.sandbox@example.com")
        self.stdout.write(f"Blog post: {post.slug}")

    def _currencies(self):
        usd, _ = Currency.objects.get_or_create(
            code="USD",
            defaults={
                "name": "US Dollar",
                "symbol": "$",
                "usd_rate": Decimal("1"),
                "is_primary": True,
                "is_active": True,
            },
        )
        if not usd.is_primary:
            usd.is_primary = True
            usd.save(update_fields=["is_primary", "updated_at"])

        Currency.objects.get_or_create(
            code="NGN",
            defaults={
                "name": "Nigerian Naira",
                "symbol": "₦",
                "usd_rate": Decimal("1600"),
                "is_primary": False,
                "is_active": True,
            },
        )
        Currency.objects.get_or_create(
            code="KES",
            defaults={
                "name": "Kenyan Shilling",
                "symbol": "KSh",
                "usd_rate": Decimal("130"),
                "is_primary": False,
                "is_active": True,
            },
        )

    def _brands(self):
        endoville, _ = Brand.objects.get_or_create(
            name="Endoville",
            defaults={"description": "Endoville Health house brand."},
        )
        nordic, _ = Brand.objects.get_or_create(
            name="Nordic Labs",
            defaults={"description": "Specialist formulations supplied to order."},
        )
        return {"endoville": endoville, "nordic": nordic}

    def _catalog_taxonomy(self):
        vitamins, _ = Category.objects.get_or_create(
            name="Vitamins",
            defaults={"description": "Daily vitamins and minerals."},
        )
        skincare, _ = Category.objects.get_or_create(
            name="Skincare",
            defaults={"description": "Topical care."},
        )
        daily, _ = Subcategory.objects.get_or_create(name="Daily", category=vitamins)
        minerals, _ = Subcategory.objects.get_or_create(name="Minerals", category=vitamins)
        treatment, _ = Subcategory.objects.get_or_create(name="Treatment", category=skincare)
        return {"daily": daily, "minerals": minerals, "treatment": treatment}

    def _products(self, brands, subcategories):
        specs = [
            {
                "key": "vitamin_d3",
                "slug": "vitamin-d3",
                "name": "Vitamin D3",
                "description": "Daily vitamin D3 for bone and immune support.",
                "brand": brands["endoville"],
                "price": Decimal("20.00"),
                "cost_price": Decimal("8.00"),
                "stock": 38,
                "sku": "VD3",
                "barcode": "5012345000142",
                "featured": True,
                "benefits": "Supports bone health and immune function.",
                "ingredients": "Vitamin D3 (cholecalciferol), olive oil, softgel capsule.",
                "how_to_use": "Take one softgel daily with food.",
                "subcategories": [subcategories["daily"]],
            },
            {
                "key": "serum",
                "slug": "specialist-serum",
                "name": "Specialist Serum",
                "description": "Concentrated serum supplied when an order is placed.",
                "brand": brands["nordic"],
                "price": Decimal("45.00"),
                "cost_price": Decimal("18.00"),
                "stock": 10,
                "sku": "SER-30",
                "barcode": "5012345000227",
                "featured": True,
                "benefits": "Hydrates and evens skin tone.",
                "ingredients": "Niacinamide, hyaluronic acid, glycerin.",
                "how_to_use": "Apply two drops to clean skin each evening.",
                "supplier_order_urls": ["https://supplier.example/order/ser-30"],
                "subcategories": [subcategories["treatment"]],
            },
            {
                "key": "magnesium",
                "slug": "magnesium-glycinate",
                "name": "Magnesium Glycinate",
                "description": "Chelated magnesium for evening use.",
                "brand": brands["endoville"],
                "price": Decimal("18.00"),
                "cost_price": Decimal("7.00"),
                "stock": 50,
                "sku": "MAG-90",
                "barcode": "5012345000302",
                "featured": False,
                "benefits": "Supports relaxation and muscle function.",
                "ingredients": "Magnesium glycinate, vegetable capsule.",
                "how_to_use": "Take two capsules in the evening.",
                "subcategories": [subcategories["minerals"]],
            },
            {
                "key": "omega",
                "slug": "omega-3",
                "name": "Omega-3",
                "description": "Fish oil capsules with EPA and DHA.",
                "brand": brands["endoville"],
                "price": Decimal("22.00"),
                "cost_price": Decimal("9.00"),
                "stock": 30,
                "sku": "OMG-60",
                "barcode": "5012345000487",
                "featured": False,
                "benefits": "Supports heart and brain health.",
                "ingredients": "Fish oil, vitamin E, softgel capsule.",
                "how_to_use": "Take one capsule daily with a meal.",
                "subcategories": [subcategories["daily"]],
            },
        ]
        products = {}
        for spec in specs:
            key = spec.pop("key")
            subcategory_list = spec.pop("subcategories")
            supplier_order_urls = spec.get("supplier_order_urls") or []
            product, created = Product.objects.get_or_create(slug=spec["slug"], defaults=spec)
            if created:
                product.subcategories.set(subcategory_list)
            elif supplier_order_urls and not product.supplier_order_urls:
                product.supplier_order_urls = supplier_order_urls
                product.save(update_fields=["supplier_order_urls", "updated_at"])
            products[key] = product
        return products

    def _variants(self, products):
        size, _ = VariationAttribute.objects.get_or_create(name="Count")
        count_60, _ = VariationOption.objects.get_or_create(attribute=size, value="60 capsules")
        count_120, _ = VariationOption.objects.get_or_create(attribute=size, value="120 capsules")
        product = products["vitamin_d3"]
        short = self._variant(
            product,
            barcode="5012345000143",
            sku="VD3-60",
            price=Decimal("20.00"),
            cost_price=Decimal("8.00"),
            stock=20,
            options=[count_60],
        )
        long = self._variant(
            product,
            barcode="5012345000144",
            sku="VD3-120",
            price=Decimal("34.00"),
            cost_price=Decimal("14.00"),
            stock=12,
            options=[count_120],
        )
        return {"d3_60": short, "d3_120": long}

    def _variant(self, product, barcode, sku, price, cost_price, stock, options):
        variant, created = ProductVariant.objects.get_or_create(
            barcode=barcode,
            defaults={
                "product": product,
                "sku": sku,
                "price": price,
                "cost_price": cost_price,
                "stock": stock,
                "is_active": True,
            },
        )
        if created:
            variant.options.set(options)
        return variant

    def _users(self, password):
        staff = self._user(
            email="sandbox.staff@endovillehealth.com",
            password=password,
            first_name="Sandbox",
            last_name="Staff",
            phone="+2348011100100",
            is_superuser=True,
        )
        ada = self._user(
            email="ada.sandbox@example.com",
            password=password,
            first_name="Ada",
            last_name="Okonkwo",
            phone="+2348011100101",
        )
        bola = self._user(
            email="bola.sandbox@example.com",
            password=password,
            first_name="Bola",
            last_name="Adeyemi",
            phone="+2348011100102",
        )
        chidi = self._user(
            email="chidi.sandbox@example.com",
            password=password,
            first_name="Chidi",
            last_name="Nwosu",
            phone="+2348011100103",
        )
        return {"staff": staff, "ada": ada, "bola": bola, "chidi": chidi}

    def _user(self, email, password, first_name, last_name, phone, is_superuser=False):
        user = User.objects.filter(email=email).first()
        if user:
            self.stdout.write(f"User already exists: {email}")
            return user
        user = User.objects.create_user(
            email=email,
            phone=phone,
            password=password,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
        )
        if is_superuser and not user.is_superuser:
            user.is_staff = True
            user.is_superuser = True
            user.save(update_fields=["is_staff", "is_superuser", "updated_at"])
        self.stdout.write(f"Created user: {email}")
        return user

    def _blog(self, product, commenter):
        category, _ = BlogCategory.objects.get_or_create(
            name="Wellness",
            defaults={"description": "Sandbox articles."},
        )
        subcategory, _ = BlogSubcategory.objects.get_or_create(
            name="Nutrition",
            category=category,
            defaults={"description": "Nutrition notes."},
        )
        author, _ = Author.objects.get_or_create(
            email="amaka.sandbox@example.com",
            defaults={
                "name": "Dr. Amaka Eze",
                "title": "Clinical advisor",
                "bio": "Sandbox author used for local content.",
            },
        )
        post, created = Post.objects.get_or_create(
            slug="why-vitamin-d3",
            defaults={
                "title": "Why vitamin D3 is a daily basic",
                "author": author,
                "content": "A short sandbox article linking vitamin D3 to the catalog.",
                "excerpt": "How to think about a daily vitamin D3 dose.",
                "is_published": True,
                "views": 12,
                "meta_keywords": "vitamin d3, sandbox",
            },
        )
        if created:
            post.subcategories.add(subcategory)
            post.related_products.add(product)
        Comment.objects.get_or_create(
            post=post,
            author=commenter,
            defaults={"content": "Helpful starting point. I ordered the 60 capsule count."},
        )
        return post

    def _cart(self, user, serum, magnesium):
        cart, _ = Cart.objects.get_or_create(user=user)
        if cart.items.exists():
            return cart
        CartItem.objects.create(cart=cart, product=serum, quantity=1)
        CartItem.objects.create(cart=cart, product=magnesium, quantity=2)
        return cart

    def _orders(self, users, products, variants):
        self._order(
            user=users["chidi"],
            note="sandbox:payment-pending",
            city="Abuja",
            address_line_1="8 Gana Street",
            shipping_fee=Decimal("5.00"),
            lines=[
                self._line(products["magnesium"], None, 1),
            ],
            payment_status=PaymentStatus.PENDING,
            payment_currency="USD",
            shipment_status=ShippingStatus.ORDER_PLACED,
        )
        self._order(
            user=users["ada"],
            note="sandbox:processing",
            city="Lagos",
            address_line_1="15 Admiralty Way",
            shipping_fee=Decimal("0.00"),
            lines=[
                self._line(products["vitamin_d3"], variants["d3_60"], 2),
            ],
            payment_status=PaymentStatus.COMPLETED,
            payment_currency="USD",
            shipment_status=ShippingStatus.ORDER_PLACED,
        )
        self._order(
            user=users["ada"],
            note="sandbox:shipping",
            city="Lagos",
            address_line_1="15 Admiralty Way",
            shipping_fee=Decimal("0.00"),
            lines=[
                self._line(products["serum"], None, 1),
            ],
            payment_status=PaymentStatus.COMPLETED,
            payment_currency="USD",
            shipment_status=ShippingStatus.DISPATCHED,
            carrier="DHL",
            tracking_number="SBX998877",
        )
        self._order(
            user=users["ada"],
            note="sandbox:complete",
            city="Lagos",
            address_line_1="15 Admiralty Way",
            shipping_fee=Decimal("0.00"),
            lines=[
                self._line(products["omega"], None, 1),
            ],
            payment_status=PaymentStatus.COMPLETED,
            payment_currency="NGN",
            shipment_status=ShippingStatus.DELIVERED,
            carrier="DHL",
            tracking_number="SBX112233",
        )

    def _line(self, product, variant, quantity):
        unit_price = variant.price if variant is not None and variant.price is not None else product.price
        description = ""
        barcode = product.barcode or ""
        if variant is not None:
            barcode = variant.barcode or barcode
            description = ", ".join(
                f"{option.attribute.name}: {option.value}"
                for option in variant.options.select_related("attribute")
            )
        return {
            "product": product,
            "variant": variant,
            "product_name": product.name,
            "variant_description": description,
            "barcode": barcode,
            "quantity": quantity,
            "unit_price": unit_price,
        }

    def _order(
        self,
        user,
        note,
        city,
        address_line_1,
        shipping_fee,
        lines,
        payment_status,
        payment_currency,
        shipment_status,
        carrier="",
        tracking_number="",
    ):
        if Order.objects.filter(notes=note).exists():
            self.stdout.write(f"Order already exists: {note}")
            return

        address = ShippingAddress.objects.create(
            user=user,
            full_name=user.get_full_name(),
            phone=user.phone or "",
            email=user.email or "",
            address_line_1=address_line_1,
            city=city,
            state=city,
            country="Nigeria",
        )
        order = Order.objects.create(
            user=user,
            shipping_address=address,
            shipping_fee=shipping_fee,
            notes=note,
            status=OrderStatus.PAYMENT_PENDING,
        )
        subtotal = Decimal("0.00")
        for line in lines:
            line_total = (line["unit_price"] * line["quantity"]).quantize(Decimal("0.01"))
            subtotal += line_total
            OrderItem.objects.create(
                order=order,
                product=line["product"],
                variant=line["variant"],
                product_name=line["product_name"],
                variant_description=line["variant_description"],
                barcode=line["barcode"],
                quantity=line["quantity"],
                unit_price=line["unit_price"],
                line_total=line_total,
            )
        order.subtotal = subtotal
        order.total = subtotal + shipping_fee
        order.save(update_fields=["subtotal", "total", "updated_at"])

        shipment = Shipment.objects.create(order=order, status=ShippingStatus.ORDER_PLACED)
        ShipmentEvent.objects.create(
            shipment=shipment,
            status=ShippingStatus.ORDER_PLACED,
            message="Order placed",
            location=city,
        )

        amount = order.total
        if payment_currency != "USD":
            amount = order_total_in_currency(order.total, payment_currency)
        OrderPayment.objects.create(
            order=order,
            provider=PaymentProvider.STRIPE,
            status=payment_status,
            amount=amount,
            currency=payment_currency,
            provider_payment_id=f"sandbox-{note.split(':', 1)[-1]}",
        )

        if shipment_status in (ShippingStatus.DISPATCHED, ShippingStatus.DELIVERED):
            order.items.update(availability=LineAvailability.CONFIRMED)

        if shipment_status == ShippingStatus.DISPATCHED:
            self._dispatch(shipment, carrier, tracking_number, city)
        elif shipment_status == ShippingStatus.DELIVERED:
            self._dispatch(shipment, carrier, tracking_number, city)
            shipment.mark_delivered()
            ShipmentEvent.objects.create(
                shipment=shipment,
                status=ShippingStatus.DELIVERED,
                message="Delivered",
                location=city,
            )
        self.stdout.write(f"Created order: {note}")

    def _dispatch(self, shipment, carrier, tracking_number, city):
        shipment.status = ShippingStatus.DISPATCHED
        shipment.carrier = carrier
        shipment.tracking_number = tracking_number
        shipment.tracking_url = f"https://track.example/{tracking_number}"
        shipment.save(update_fields=["status", "carrier", "tracking_number", "tracking_url", "updated_at"])
        ShipmentEvent.objects.create(
            shipment=shipment,
            status=ShippingStatus.DISPATCHED,
            message="Dispatched",
            location="Lagos WH",
        )

    def _review(self, user, product):
        order = Order.objects.filter(notes="sandbox:complete", user=user).first()
        if order is None:
            return
        ProductReview.objects.get_or_create(
            product=product,
            user=user,
            defaults={
                "order": order,
                "rating": 5,
                "body": "Arrived sealed and as described.",
                "is_anonymous": False,
            },
        )

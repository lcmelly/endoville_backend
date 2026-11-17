"""
Load brands, categories, subcategories, and products from a JSON file.

    python manage.py seed_products
    python manage.py seed_products --path "../seed/products seed.json"

Brands and categories match on name. Products match on SKU, then slug.
Running it again updates those records instead of inserting duplicates.
"""

import json
from decimal import Decimal
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from products.models import Brand, Category, Product, Subcategory

DEFAULT_PATH = Path(__file__).resolve().parents[4] / "seed" / "products seed.json"


class Command(BaseCommand):
    help = "Insert or update catalog rows from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT_PATH), help="Path to the product JSON file.")

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["path"]).expanduser()
        if not path.is_file():
            raise CommandError(f"Product seed file not found: {path}")
        data = json.loads(path.read_text())
        if not isinstance(data, dict):
            raise CommandError("Product seed file must be an object with brands, categories, and products.")

        brands = self._brands(data.get("brands") or [])
        subcategories = self._categories(data.get("categories") or [])
        count = 0
        for row in data.get("products") or []:
            self._product(row, brands, subcategories)
            count += 1
        self.stdout.write(
            self.style.SUCCESS(
                f"Seeded {len(brands)} brands, {len(subcategories)} subcategories, and {count} products."
            )
        )

    def _brands(self, rows):
        brands = {}
        for row in rows:
            name = (row.get("name") or "").strip()
            if not name:
                raise CommandError("Each brand needs a name.")
            description = (row.get("description") or "").strip()
            image_urls = list(row.get("image_urls") or [])
            image_refs = list(row.get("image_refs") or [])
            image_labels = list(row.get("image_labels") or [])
            brand = Brand.objects.filter(name=name).order_by("pk").first()
            if brand is None:
                brand = Brand.objects.create(
                    name=name,
                    description=description,
                    image_urls=image_urls,
                    image_refs=image_refs,
                    image_labels=image_labels,
                )
            else:
                changed = []
                if description and brand.description != description:
                    brand.description = description
                    changed.append("description")
                if image_urls and brand.image_urls != image_urls:
                    brand.image_urls = image_urls
                    changed.append("image_urls")
                if image_refs and brand.image_refs != image_refs:
                    brand.image_refs = image_refs
                    changed.append("image_refs")
                if image_labels and brand.image_labels != image_labels:
                    brand.image_labels = image_labels
                    changed.append("image_labels")
                if changed:
                    brand.save(update_fields=changed)
            brands[name] = brand
        return brands

    def _categories(self, rows):
        subcategories = {}
        for row in rows:
            name = (row.get("name") or "").strip()
            if not name:
                raise CommandError("Each category needs a name.")
            description = (row.get("description") or "").strip()
            category, created = Category.objects.get_or_create(
                name=name,
                defaults={"description": description},
            )
            if not created and description:
                category.description = description
                category.save(update_fields=["description"])
            for sub in row.get("subcategories") or []:
                sub_name = (sub.get("name") or "").strip()
                if not sub_name:
                    raise CommandError(f"Category {name} has a subcategory without a name.")
                subcategory, _ = Subcategory.objects.get_or_create(name=sub_name, category=category)
                subcategories[(name, sub_name)] = subcategory
        return subcategories

    def _product(self, row, brands, subcategories):
        name = (row.get("name") or "").strip()
        slug = (row.get("slug") or "").strip()
        sku = (row.get("sku") or "").strip()
        description = (row.get("description") or "").strip()
        if not name or not slug or not description:
            raise CommandError("Each product needs a name, slug, and description.")
        brand_name = (row.get("brand") or "").strip()
        brand = brands.get(brand_name)
        if brand is None:
            raise CommandError(f"{name} refers to unknown brand {brand_name}.")
        category_name = (row.get("category") or "").strip()
        linked = []
        for sub_name in row.get("subcategories") or []:
            key = (category_name, sub_name.strip())
            subcategory = subcategories.get(key)
            if subcategory is None:
                raise CommandError(f"{name} refers to unknown subcategory {sub_name}.")
            linked.append(subcategory)

        product = Product.objects.filter(sku=sku).order_by("pk").first() if sku else None
        if product is None:
            product = Product.objects.filter(slug=slug).first()
        if product is None:
            product = Product(sku=sku or None, slug=slug)
        product.name = name
        product.description = description
        product.benefits = (row.get("benefits") or "").strip()
        product.ingredients = (row.get("ingredients") or "").strip()
        product.how_to_use = (row.get("how_to_use") or "").strip()
        product.meta_title = ((row.get("meta_title") or name).strip())[:255]
        product.meta_description = ((row.get("meta_description") or description).strip())[:300]
        if row.get("unit_weight"):
            product.unit_weight = int(row["unit_weight"])
        barcode = (row.get("barcode") or "").strip()
        if barcode:
            product.barcode = barcode
        product.brand = brand
        product.price = Decimal(str(row.get("price") or "0"))
        product.sku = sku or None
        product.slug = slug
        product.image_urls = list(row.get("image_urls") or [])
        product.supplier_order_urls = list(row.get("supplier_order_urls") or [])
        product.save()
        product.subcategories.set(linked)
        return product

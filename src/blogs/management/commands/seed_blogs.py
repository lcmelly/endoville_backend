"""
Load published blog posts from a JSON file.

    python manage.py seed_blogs
    python manage.py seed_blogs --path "../seed/blogs seed.json"

Matched on slug. Running it again updates the title, body, excerpt, image, category,
and related products. Related products are matched by SKU from the product catalog.
"""

import json
import re
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from blogs.models import Author, Category, Post, Subcategory
from products.models import Product

DEFAULT_PATH = Path(__file__).resolve().parents[4] / "seed" / "blogs seed.json"
AUTHOR_EMAIL = "editorial@endovillehealth.com"
IMAGE = re.compile(r"!\[([^\]]*)\]\(([^)]+)\)")


class Command(BaseCommand):
    help = "Insert or update blog posts from a JSON file."

    def add_arguments(self, parser):
        parser.add_argument("--path", default=str(DEFAULT_PATH), help="Path to the blog JSON file.")

    @transaction.atomic
    def handle(self, *args, **options):
        path = Path(options["path"]).expanduser()
        if not path.is_file():
            raise CommandError(f"Blog seed file not found: {path}")
        rows = json.loads(path.read_text())
        if not isinstance(rows, list):
            raise CommandError("Blog seed file must be a list of posts.")

        author, _ = Author.objects.get_or_create(
            email=AUTHOR_EMAIL,
            defaults={
                "name": "Endoville Health",
                "title": "Editorial",
                "bio": "Health guides from Endoville.",
            },
        )
        slugs = []
        for row in rows:
            post = self._upsert(author, row)
            slugs.append(post.slug)
        self.stdout.write(self.style.SUCCESS(f"Seeded {len(slugs)} blog posts."))
        for slug in slugs:
            self.stdout.write(slug)

    def _upsert(self, author, row):
        title = (row.get("title") or "").strip()
        slug = (row.get("slug") or "").strip()
        body = row.get("markdown_body") or ""
        if not title or not slug or not body:
            raise CommandError("Each post needs a title, slug, and markdown_body.")
        category_name = (row.get("category") or "Wellness").strip()
        category, _ = Category.objects.get_or_create(name=category_name)
        subcategory, _ = Subcategory.objects.get_or_create(name=category_name, category=category)
        image = IMAGE.search(body)
        excerpt = (row.get("meta_description") or "").strip()[:160]
        keywords = (row.get("meta_title") or "").strip()[:255]
        defaults = {
            "title": title[:200],
            "author": author,
            "content": body,
            "excerpt": excerpt,
            "featured_image_url": image.group(2).strip() if image else "",
            "featured_image_alt": image.group(1).strip()[:255] if image else "",
            "meta_keywords": keywords,
            "is_published": True,
        }
        post, created = Post.objects.get_or_create(slug=slug, defaults=defaults)
        if not created:
            for field, value in defaults.items():
                setattr(post, field, value)
            post.save()
        post.subcategories.set([subcategory])
        skus = [str(sku).strip() for sku in (row.get("related_product_skus") or []) if str(sku).strip()]
        found = {product.sku: product for product in Product.objects.filter(sku__in=skus)}
        post.related_products.set([found[sku] for sku in skus if sku in found])
        return post

from django.core.management import call_command

import pytest

from blogs.models import Post

pytestmark = pytest.mark.django_db


def test_seed_blogs_loads_the_json_file():
    call_command("seed_products")
    call_command("seed_blogs")
    call_command("seed_blogs")

    posts = Post.objects.filter(is_published=True)
    assert posts.count() == 6
    post = posts.get(slug="the-equatorial-paradox-why-do-so-many-kenyans-have-low-vitamin-d")
    assert post.author.email == "editorial@endovillehealth.com"
    assert post.subcategories.get().category.name == "Vitamins & Minerals"
    assert post.excerpt
    assert "Vitamin D" in post.content
    assert post.featured_image_url.startswith("https://images.unsplash.com/")
    assert list(post.related_products.order_by("sku").values_list("sku", flat=True)) == [
        "IHR-10056",
        "IHR-124743",
        "IHR-70316",
        "IHR-77548",
    ]
    assert all(post.related_products.exists() for post in posts)
    assert not posts.filter(featured_image_url="").exists()

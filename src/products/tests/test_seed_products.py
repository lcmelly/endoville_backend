import json
from pathlib import Path

import pytest
from django.core.management import call_command

from products.models import Brand

pytestmark = pytest.mark.django_db


def test_seed_products_writes_brand_images(tmp_path: Path):
    path = tmp_path / "products.json"
    path.write_text(
        json.dumps(
            {
                "brands": [
                    {
                        "name": "Endoville",
                        "description": "Endoville Health house brand.",
                        "image_urls": ["https://endovillehealth.com/logo_white.png"],
                        "image_refs": ["logo_white.png"],
                        "image_labels": ["logo_white"],
                    }
                ],
                "categories": [],
                "products": [],
            }
        )
    )

    call_command("seed_products", path=str(path))
    call_command("seed_products", path=str(path))

    brand = Brand.objects.get(name="Endoville")
    assert brand.image_urls == ["https://endovillehealth.com/logo_white.png"]
    assert brand.image_refs == ["logo_white.png"]
    assert brand.image_labels == ["logo_white"]
    assert Brand.objects.filter(name="Endoville").count() == 1

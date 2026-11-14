from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("blogs", "0005_post_featured_image_url"),
    ]

    operations = [
        migrations.AlterField(
            model_name="post",
            name="slug",
            field=models.SlugField(blank=True, max_length=200, unique=True),
        ),
    ]

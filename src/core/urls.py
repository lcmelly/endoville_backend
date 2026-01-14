"""
URL configuration for core project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
import os

from django.conf import settings
from django.contrib import admin
from django.http import Http404
from django.urls import include, path, re_path
from django.views.generic import RedirectView
from django.views.static import serve
from django.utils._os import safe_join

def docs_serve(request, path="index.html"):
    """
    Serve built docs from the /site directory, defaulting to index.html for directories.
    """
    if not path or path.endswith("/"):
        path = f"{path}index.html" if path else "index.html"

    doc_root = settings.BASE_DIR / "site"
    try:
        fullpath = safe_join(str(doc_root), path)
    except ValueError:
        raise Http404("Invalid path")

    if not fullpath or not os.path.exists(fullpath):
        raise Http404("Documentation not found")

    return serve(request, path, document_root=doc_root)


urlpatterns = [
    path('', RedirectView.as_view(url='/docs/', permanent=False)),
    path('docs/', docs_serve, name='docs-index'),
    re_path(r'^docs/(?P<path>.*)$', docs_serve),
    path('admin/', admin.site.urls),
    path('api/users/', include('users.urls')),
    path('api/blogs/', include('blogs.urls')),
]

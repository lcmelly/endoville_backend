import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from blogs.models import Author, Comment, Post
from blogs.serializers import PostSerializer
from users.models import CustomUser


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def staff_user():
    return CustomUser.objects.create_user(
        email="staff@example.com",
        password="strongpass",
        is_active=True,
        is_staff=True,
    )


@pytest.fixture
def user():
    return CustomUser.objects.create_user(
        email="user@example.com",
        password="strongpass",
        is_active=True,
    )


@pytest.fixture
def author():
    return Author.objects.create(
        name="Dr. Jane Doe",
        title="Chief Medical Officer",
        email="jane@example.com",
        bio="Bio",
    )


@pytest.fixture
def post(author):
    return Post.objects.create(
        title="Sample Post",
        slug="sample-post",
        author=author,
        content="Body",
        excerpt="Excerpt",
        meta_keywords="key",
        is_published=True,
    )


def test_urls_resolve():
    assert reverse("blogs:post-list") == "/api/blogs/posts/"
    assert reverse("blogs:author-list") == "/api/blogs/authors/"
    assert reverse("blogs:comment-list") == "/api/blogs/comments/"


def test_post_serializer_includes_author_name(author, post):
    data = PostSerializer(instance=post).data
    assert data["author_name"] == author.name


def test_posts_list_public(api_client):
    resp = api_client.get("/api/blogs/posts/")
    assert resp.status_code == status.HTTP_200_OK


def test_posts_create_requires_staff(api_client, user, staff_user, author):
    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/blogs/posts/",
        {
            "title": "New Post",
            "author": author.id,
            "content": "Body",
            "excerpt": "SEO",
            "meta_keywords": "a,b",
            "is_published": False,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    resp = api_client.post(
        "/api/blogs/posts/",
        {
            "title": "Staff Post",
            "author": author.id,
            "content": "Body",
            "excerpt": "SEO",
            "meta_keywords": "a,b",
            "is_published": True,
        },
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED


def test_comments_create_permissions(api_client, post, user):
    resp = api_client.post(
        "/api/blogs/comments/",
        {"post": post.id, "content": "Nice"},
        format="json",
    )
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    api_client.force_authenticate(user=user)
    resp = api_client.post(
        "/api/blogs/comments/",
        {"post": post.id, "content": "Nice"},
        format="json",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    assert Comment.objects.filter(post=post, author=user, content="Nice").exists()


def test_comment_owner_and_staff_delete(api_client, post, user, staff_user):
    comment = Comment.objects.create(post=post, author=user, content="c1")

    other = CustomUser.objects.create_user(
        email="other@example.com", password="pass", is_active=True
    )
    api_client.force_authenticate(user=other)
    resp = api_client.delete(f"/api/blogs/comments/{comment.id}/")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=user)
    resp = api_client.delete(f"/api/blogs/comments/{comment.id}/")
    assert resp.status_code == status.HTTP_204_NO_CONTENT

    comment2 = Comment.objects.create(post=post, author=user, content="c2")
    api_client.force_authenticate(user=staff_user)
    resp = api_client.delete(f"/api/blogs/comments/{comment2.id}/")
    assert resp.status_code == status.HTTP_204_NO_CONTENT


def test_comment_update_only_staff(api_client, post, user, staff_user):
    comment = Comment.objects.create(post=post, author=user, content="orig")

    api_client.force_authenticate(user=user)
    resp = api_client.patch(
        f"/api/blogs/comments/{comment.id}/", {"content": "new"}, format="json"
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    api_client.force_authenticate(user=staff_user)
    resp = api_client.patch(
        f"/api/blogs/comments/{comment.id}/", {"content": "staff"}, format="json"
    )
    assert resp.status_code == status.HTTP_200_OK
    comment.refresh_from_db()
    assert comment.content == "staff"

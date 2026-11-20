"""Helper for the rule that one user's data is never shown to another."""

from rest_framework.test import APIClient


def assert_hidden_from(other_client: APIClient, list_url: str, pk: int) -> None:
    """Assert that the object ``pk`` behind ``list_url`` does not exist for another user.

    Use this in the tests of every endpoint that serves user-owned data.
    """
    listing = other_client.get(list_url)
    assert listing.status_code == 200
    assert listing.json() == []
    assert other_client.delete(f"{list_url}{pk}/").status_code == 404

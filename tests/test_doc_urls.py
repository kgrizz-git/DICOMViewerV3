"""
Unit tests for utils.doc_urls (GitHub user-docs URL builders).
"""

from __future__ import annotations

from utils.doc_urls import USER_DOCS_GITHUB_PREFIX, user_doc_url, user_guide_hub_url


def test_user_doc_url_builds_full_url():
    assert user_doc_url("USER_GUIDE.md") == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE.md"


def test_user_doc_url_strips_leading_slash():
    assert user_doc_url("/USER_GUIDE_MPR.md") == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE_MPR.md"


def test_user_doc_url_strips_whitespace():
    assert user_doc_url("  USER_GUIDE.md  ") == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE.md"


def test_user_guide_hub_url():
    assert user_guide_hub_url() == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE.md"

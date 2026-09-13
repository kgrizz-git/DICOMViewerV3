"""
Unit tests for utils.doc_urls (GitHub user-docs URL builders).
"""

from __future__ import annotations

from utils.doc_urls import (
    GITHUB_BLOB_BASE,
    USER_DOCS_GITHUB_PREFIX,
    repo_blob_url,
    user_doc_url,
    user_guide_hub_url,
)


def test_user_docs_prefix_derives_from_blob_base():
    expected = f"{GITHUB_BLOB_BASE}/user-docs"
    assert expected == USER_DOCS_GITHUB_PREFIX


def test_repo_blob_url_builds_changelog_path():
    assert repo_blob_url("CHANGELOG.md") == f"{GITHUB_BLOB_BASE}/CHANGELOG.md"


def test_repo_blob_url_strips_leading_slash():
    assert (
        repo_blob_url("/dev-docs/info/FOO.md")
        == f"{GITHUB_BLOB_BASE}/dev-docs/info/FOO.md"
    )


def test_user_doc_url_builds_full_url():
    assert user_doc_url("USER_GUIDE.md") == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE.md"


def test_user_doc_url_strips_leading_slash():
    assert user_doc_url("/USER_GUIDE_MPR.md") == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE_MPR.md"


def test_user_doc_url_strips_whitespace():
    assert user_doc_url("  USER_GUIDE.md  ") == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE.md"


def test_user_guide_hub_url():
    assert user_guide_hub_url() == f"{USER_DOCS_GITHUB_PREFIX}/USER_GUIDE.md"

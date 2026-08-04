"""Focused behavior tests for the bundled fusion technical documentation dialog."""

from __future__ import annotations

import pytest

from gui.dialogs.fusion_technical_doc_dialog import (
    FusionTechnicalDocDialog,
    _extract_toc_sections,
    _normalize_doc_text_encoding,
)


class _Config:
    def __init__(self, theme: str) -> None:
        self.theme = theme

    def get_theme(self) -> str:
        return self.theme


def test_normalization_and_toc_extraction_handle_duplicate_links() -> None:
    html = '<h2>Table of Contents</h2><ul><li><a href="#one"> One </a></li><li><a href="#one">Again</a></li></ul>â†’'

    normalized = _normalize_doc_text_encoding(html)

    assert "&rarr;" in normalized
    assert _extract_toc_sections(normalized) == [("one", "One")]


@pytest.mark.qt
def test_light_document_constructs_searches_and_resets(qapp) -> None:
    FusionTechnicalDocDialog._content_cache.clear()
    dialog = FusionTechnicalDocDialog(_Config("light"))

    assert "background-color: #ffffff" in dialog.styleSheet()
    assert dialog._section_anchors
    dialog._on_search_text_changed("fusion")
    assert dialog._search_match_positions
    assert dialog.next_button.isEnabled()
    dialog._on_search_text_changed("")
    assert dialog._search_match_positions == []
    assert dialog.next_button.isEnabled() is False

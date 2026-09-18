from intelligence_content_engine.language import ContentLanguage
from intelligence_content_engine.output.docx_writer import markdown_to_docx, save_article_docx


def test_telugu_docx_uses_unicode_font_hint():
    document = markdown_to_docx(
        "# తెలుగు డాక్యుమెంట్\n\nతెలుగు కంటెంట్.",
        "తెలుగు డాక్యుమెంట్",
        ContentLanguage.TELUGU,
    )
    assert document.styles["Normal"].font.name == "Nirmala UI"


def test_tamil_docx_uses_unicode_font_hint():
    document = markdown_to_docx(
        "# தமிழ் ஆவணம்\n\nதமிழ் உள்ளடக்கம்.",
        "தமிழ் ஆவணம்",
        ContentLanguage.TAMIL,
    )
    assert document.styles["Normal"].font.name == "Nirmala UI"


def test_language_suffix_is_used_for_non_english_output(tmp_path):
    path = save_article_docx("తెలుగు", "Test Article", output_dir=str(tmp_path), language=ContentLanguage.TELUGU)
    assert path is not None
    assert path.name == "test-article-telugu.docx"

from intelligence_content_engine.language import ContentLanguage


def test_supported_content_languages():
    assert ContentLanguage.parse("english") is ContentLanguage.ENGLISH
    assert ContentLanguage.parse("TELUGU") is ContentLanguage.TELUGU
    assert ContentLanguage.parse("Tamil") is ContentLanguage.TAMIL
    assert ContentLanguage.parse("Kannada") is ContentLanguage.KANNADA
    assert ContentLanguage.parse("MALAYALAM") is ContentLanguage.MALAYALAM


def test_invalid_content_language_has_actionable_error():
    try:
        ContentLanguage.parse("hindi")
    except ValueError as exc:
        assert "english" in str(exc)
        assert "telugu" in str(exc)
        assert "tamil" in str(exc)
        assert "kannada" in str(exc)
        assert "malayalam" in str(exc)
    else:
        raise AssertionError("Expected invalid language to raise ValueError")

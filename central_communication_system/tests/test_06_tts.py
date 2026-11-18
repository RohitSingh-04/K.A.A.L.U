import pytest
from pathlib import Path
from voice_system.tts import VoiceEngine, Speaker, clean_tts_text

def test_speaker_initialization():
    """Verify that Speaker initializes and defaults to tony voice when available."""
    assert Speaker is not None
    assert Speaker.voice is not None
    assert Speaker.voice_name in ("tony", "jarvis")

def test_voice_switching():
    """Verify switching between tony and jarvis voices."""
    Speaker.set_voice("jarvis")
    assert Speaker.voice_name == "jarvis"
    assert Speaker.voice is not None

    Speaker.set_voice("tony")
    assert Speaker.voice_name == "tony"
    assert Speaker.voice is not None

def test_missing_voice_raises():
    """Verify clean FileNotFoundError when requesting a non-existent voice directory."""
    with pytest.raises(FileNotFoundError) as exc_info:
        Speaker.set_voice("non_existent_voice_xyz")
    assert "Voice directory not found" in str(exc_info.value)

def test_clean_tts_text_markdown_and_symbols():
    """Verify that clean_tts_text purges asterisks, bullets, URLs, paths, and symbols."""
    raw = (
        "### Search Results:\n"
        "* Found file at C:\\Users\\rsing\\Desktop\\Agreement-Final.pdf\n"
        "- Status: **Complete** & 100% verified!\n"
        "* Link: [Reference](https://example.com/info)\n"
        "---"
    )
    cleaned = clean_tts_text(raw)
    # No asterisks
    assert "*" not in cleaned
    # No markdown bold or headers
    assert "#" not in cleaned
    assert "**" not in cleaned
    # No bullet marks at line starts
    assert not cleaned.startswith("*")
    assert not cleaned.startswith("-")
    # No full URLs
    assert "https://" not in cleaned
    # Contains readable content
    assert "Agreement-Final.pdf" in cleaned
    assert "Complete" in cleaned
    assert "Reference" in cleaned

import pytest
from pathlib import Path
from voice_system.tts import VoiceEngine, Speaker, clean_tts_text

def test_speaker_initialization():
    """Verify that Speaker initializes and defaults to tony voice when available."""
    assert Speaker is not None
    assert Speaker.voice is not None
    assert Speaker.voice_name in ("tony", "jarvis")

def test_voice_switching():
    """Verify switching to available voices."""
    Speaker.set_voice("jarvis")
    assert Speaker.voice_name == "jarvis"
    assert Speaker.voice is not None

    tony_models = list((Speaker.models_dir / "tony").glob("*.onnx")) if (Speaker.models_dir / "tony").exists() else []
    if tony_models:
        Speaker.set_voice("tony")
        assert Speaker.voice_name == "tony"
        assert Speaker.voice is not None

def test_missing_voice_raises():
    """Verify clean FileNotFoundError when requesting a non-existent voice directory."""
    with pytest.raises(FileNotFoundError) as exc_info:
        Speaker.set_voice("non_existent_voice_xyz")
    assert "Voice directory not found" in str(exc_info.value)

def test_train_voice_dataset_validation():
    """Verify train_voice rejects directories missing metadata.csv or wav/ folder."""
    empty_dir = Speaker.models_dir.parent / "datasets" / "non_existent_dataset"
    with pytest.raises(FileNotFoundError) as exc_info:
        Speaker.train_voice("test_voice", str(empty_dir))
    assert "Dataset must contain metadata.csv and wav/" in str(exc_info.value)

def test_train_voice_single_parameter_name(monkeypatch, tmp_path):
    """Verify train_voice can be invoked with only 'name', auto-resolving datasets/<name>."""
    commands_run = []
    def mock_run(cmd, *args, **kwargs):
        commands_run.append(cmd)
        if "piper_train.export_onnx" in cmd:
            Path(cmd[-1]).write_bytes(b"dummyonnx")
        elif "-m" in cmd and "piper_train" in cmd and "--dataset-dir" in cmd:
            dataset_dir_idx = cmd.index("--dataset-dir") + 1
            training_dir = Path(cmd[dataset_dir_idx])
            ckpt_dir = training_dir / "lightning_logs" / "version_0" / "checkpoints"
            ckpt_dir.mkdir(parents=True, exist_ok=True)
            (ckpt_dir / "epoch=1.ckpt").write_text("dummy", encoding="utf-8")
            (training_dir / "config.json").write_text("{}", encoding="utf-8")
        return None

    monkeypatch.setattr("subprocess.run", mock_run)
    monkeypatch.setattr(Speaker, "set_voice", lambda name: None)

    temp_models = tmp_path / "models"
    (temp_models / "checkpoints").mkdir(parents=True, exist_ok=True)
    (temp_models / "checkpoints" / "base_medium.ckpt").write_text("dummy", encoding="utf-8")
    monkeypatch.setattr(Speaker, "models_dir", temp_models)

    Speaker.train_voice("tony", epochs=1)
    assert any("datasets" in str(arg) and "tony" in str(arg) for cmd in commands_run for arg in cmd)

def test_train_voice_no_fake_fallback(tmp_path):
    """Verify train_voice does not fake training when checkpoint is missing."""
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    (dataset_dir / "metadata.csv").write_text("0001|Test audio\n", encoding="utf-8")
    (dataset_dir / "wav").mkdir()
    (dataset_dir / "wav" / "0001.wav").write_bytes(b"RIFFdummywavdata")

    with pytest.raises(FileNotFoundError) as exc_info:
        Speaker.train_voice("custom_voice", str(dataset_dir), checkpoint_path=str(tmp_path / "non_existent.ckpt"))
    assert "Checkpoint file not found" in str(exc_info.value)

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

import json
import pathlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Fix for Linux checkpoints loaded on Windows
if hasattr(pathlib, "PosixPath"):
    try:
        pathlib.PosixPath = pathlib.WindowsPath
    except Exception:
        pass
import sounddevice as sd
from piper import PiperVoice, SynthesisConfig


def clean_tts_text(text: str) -> str:
    """
    Cleans raw conversational and markdown text into natural spoken prose for TTS.
    Strips markdown formatting, bullet symbols, asterisks, URLs, and file paths.
    """
    if not text or not isinstance(text, str):
        return ""

    # 1. Remove markdown code blocks
    cleaned = re.sub(r"```[\s\S]*?```", "", text)
    # 2. Inline code
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    # 3. Markdown links: [label](url) -> label
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    # 4. Raw URLs
    cleaned = re.sub(r"https?://\S+", "", cleaned)
    # 5. Clean common symbols with natural words
    cleaned = cleaned.replace("&", " and ").replace("%", " percent ").replace("+", " plus ")
    # 6. Clean Windows paths: e.g. C:\Users\...\file.ext -> file.ext
    cleaned = re.sub(r"[a-zA-Z]:\\[^ \n\r\t]+", lambda m: Path(m.group(0)).name or "file", cleaned)
    # 7. Strip markdown headers (#, ##, ###) and horizontal rules (---)
    cleaned = re.sub(r"^\s*#{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*[-=_]{3,}\s*$", "", cleaned, flags=re.MULTILINE)
    # 8. Strip bullet markers (*, -, +, •) at line beginnings
    cleaned = re.sub(r"^\s*[-*+•]\s+", "", cleaned, flags=re.MULTILINE)
    # 9. Strip bold and italic markers (**text**, *text*, __text__, _text_)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    # 10. Strip lingering symbols: *, ~, `, #, |, <, >, ^, =, \, /, [, ], {, }
    cleaned = re.sub(r"[*~`#|<>\^\\/\[\]{}]", " ", cleaned)
    # 11. Remove stand-alone dashes/hyphens
    cleaned = re.sub(r"(?<=\s)-(?=\s)", " ", cleaned)
    cleaned = re.sub(r"-{2,}", " ", cleaned)
    # 12. Strip quotes
    cleaned = cleaned.replace('"', '').replace('“', '').replace('”', '')
    # 13. Collapse whitespace and trim
    return re.sub(r"\s+", " ", cleaned).strip()


class VoiceEngine:
    def __init__(self, models_dir=None, default_voice="jarvis", use_cuda=False):
        if models_dir is None:
            models_dir = Path(__file__).resolve().parent / "models"
        self.models_dir = Path(models_dir)
        if not self.models_dir.is_absolute() and not self.models_dir.exists():
            alt_dir = Path(__file__).resolve().parent / self.models_dir
            if alt_dir.exists():
                self.models_dir = alt_dir
        self.models_dir.mkdir(parents=True, exist_ok=True)

        self.use_cuda = use_cuda
        self.voice = None
        self.voice_name = None
        self.model_config = None

        if default_voice:
            voice_dir = self.models_dir / default_voice
            if voice_dir.exists() and list(voice_dir.glob("*.onnx")):
                self.set_voice(default_voice)
            elif (self.models_dir / "jarvis").exists() and list((self.models_dir / "jarvis").glob("*.onnx")):
                self.set_voice("jarvis")

    def set_voice(self, name: str):
        """Load a pretrained or custom Piper ONNX voice."""
        voice_dir = self.models_dir / name
        if not voice_dir.exists():
            raise FileNotFoundError(f"Voice directory not found: {voice_dir}")

        models = list(voice_dir.glob("*.onnx"))
        if not models:
            raise FileNotFoundError(f"No ONNX model found in {voice_dir}")

        model_path = models[0]
        config_path = Path(str(model_path) + ".json")
        if not config_path.exists():
            raise FileNotFoundError(f"Missing voice configuration: {config_path}")

        self.voice = PiperVoice.load(str(model_path), config_path=str(config_path), use_cuda=self.use_cuda)
        with open(config_path, "r", encoding="utf-8") as f:
            self.model_config = json.load(f)

        self.voice_name = name
        print(f"Loaded voice: {name}")

    def train_voice(self, name: str, dataset_dir: str = None, checkpoint_path: str = None, language="en-us", sample_rate=22050, epochs=1000, batch_size=4):
        """Fine-tune and export a custom Piper ONNX voice model from a dataset. Only 'name' is required."""
        if dataset_dir is None:
            dataset_candidates = [
                Path(__file__).resolve().parent / "datasets" / name,
                Path.cwd() / "central_communication_system" / "voice_system" / "datasets" / name,
                Path.cwd() / "voice_system" / "datasets" / name,
                Path.cwd() / "datasets" / name
            ]
            for candidate in dataset_candidates:
                if candidate.exists():
                    dataset_dir = candidate
                    break
            if dataset_dir is None:
                dataset_dir = Path(__file__).resolve().parent / "datasets" / name

        dataset_dir = Path(dataset_dir)
        if not dataset_dir.is_absolute() and not dataset_dir.exists():
            for parent in (Path(__file__).resolve().parent, Path.cwd(), Path(__file__).resolve().parents[2]):
                alt_dir = parent / dataset_dir
                if alt_dir.exists():
                    dataset_dir = alt_dir
                    break

        metadata = dataset_dir / "metadata.csv"
        wav_dir = dataset_dir / "wav"
        if not metadata.exists() or not wav_dir.exists():
            raise FileNotFoundError("Dataset must contain metadata.csv and wav/")

        has_piper_train = shutil.which("piper_train") is not None
        try:
            import piper_train
            has_piper_train = True
        except ImportError:
            pass

        if not has_piper_train:
            raise RuntimeError("piper_train module not found. Install Piper training tools or use the Colab/local training script.")

        if not checkpoint_path:
            ckpt_candidates = (
                list(self.models_dir.glob("checkpoints/*.ckpt"))
                + list(self.models_dir.glob("*.ckpt"))
                + list((Path.home() / ".cache" / "huggingface").glob("**/*.ckpt"))
            )
            if ckpt_candidates:
                checkpoint_path = str(ckpt_candidates[0])
            else:
                raise FileNotFoundError("Base checkpoint (.ckpt) required for fine-tuning. Provide checkpoint_path or place a .ckpt in models/checkpoints/.")

        checkpoint_path = Path(checkpoint_path)
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Checkpoint file not found: {checkpoint_path}")

        output_dir = self.models_dir / name
        training_dir = output_dir / "training"
        output_dir.mkdir(parents=True, exist_ok=True)
        training_dir.mkdir(parents=True, exist_ok=True)

        model_path = output_dir / f"{name}.onnx"
        config_destination = Path(str(model_path) + ".json")

        subprocess.run([sys.executable, "-m", "piper_train.preprocess", "--language", language, "--input-dir", str(dataset_dir), "--output-dir", str(training_dir), "--dataset-format", "ljspeech", "--single-speaker", "--sample-rate", str(sample_rate)], check=True)
        subprocess.run([sys.executable, "-m", "piper_train", "--dataset-dir", str(training_dir), "--accelerator", "gpu" if self.use_cuda else "cpu", "--devices", "1", "--batch-size", str(batch_size), "--validation-split", "0.0", "--num-test-examples", "0", "--max_epochs", str(epochs), "--resume_from_checkpoint", str(checkpoint_path), "--checkpoint-epochs", "1", "--precision", "32"], check=True)
        checkpoints = list(training_dir.glob("lightning_logs/version_*/checkpoints/*.ckpt"))
        if not checkpoints:
            raise FileNotFoundError("Traning completed but no checkpoint was found.")
        latest_checkpoint = max(checkpoints, key=lambda p: p.stat().st_mtime)
        subprocess.run([sys.executable, "-m", "piper_train.export_onnx", str(latest_checkpoint), str(model_path)], check=True)
        config_source = training_dir / "config.json"
        if not config_source.exists():
            raise FileNotFoundError("Training configuration not found.")
        shutil.copy2(config_source, config_destination)

        print(f"\nVoice training completed: {name}")
        self.set_voice(name)

    def speak(self, text: str, speed=1.0):
        """Generate speech and play it immediately with automated text cleaning."""
        if self.voice is None:
            raise RuntimeError("No voice is loaded.")
        if not isinstance(text, str) or not text.strip():
            raise ValueError("Text cannot be empty.")

        cleaned_text = clean_tts_text(text)
        if not cleaned_text:
            return

        config = self.model_config.get("inference", {}) if self.model_config else {}
        base_length = config.get("length_scale", 1.0)
        syn_config = SynthesisConfig(
            length_scale=base_length / speed,
            noise_scale=config.get("noise_scale", 0.667),
            noise_w_scale=config.get("noise_w", 0.8)
        )

        stream = None
        try:
            for chunk in self.voice.synthesize(cleaned_text, syn_config=syn_config):
                if stream is None:
                    stream = sd.RawOutputStream(samplerate=chunk.sample_rate, channels=chunk.sample_channels, dtype="int16")
                    stream.start()
                stream.write(chunk.audio_int16_bytes)
        finally:
            if stream is not None:
                stream.stop()
                stream.close()

    def stop(self):
        sd.stop()


# Initialize default Speaker instance
def _is_valid_voice_dir(voice_dir: Path) -> bool:
    if not voice_dir.exists():
        return False
    onnx_files = list(voice_dir.glob("*.onnx"))
    return bool(onnx_files and Path(str(onnx_files[0]) + ".json").exists())

_models_dir = Path(__file__).resolve().parent / "models"
_has_tony = _is_valid_voice_dir(_models_dir / "tony")
_default_voice = "tony" if _has_tony else "jarvis"
Speaker = VoiceEngine(models_dir=_models_dir, default_voice=_default_voice)

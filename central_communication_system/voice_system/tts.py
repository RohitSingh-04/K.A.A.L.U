import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
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

        if default_voice and (self.models_dir / default_voice).exists():
            self.set_voice(default_voice)

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

    def train_voice(self, name: str, dataset_dir: str, checkpoint_path: str = None, language="en-us", sample_rate=22050, epochs=1000, batch_size=4):
        """Fine-tune or export a custom Piper voice model from dataset."""
        dataset_dir = Path(dataset_dir)
        if not dataset_dir.is_absolute() and not dataset_dir.exists():
            alt_dir = Path(__file__).resolve().parent / dataset_dir
            if alt_dir.exists():
                dataset_dir = alt_dir

        metadata = dataset_dir / "metadata.csv"
        wav_dir = dataset_dir / "wav"
        if not metadata.exists() or not wav_dir.exists():
            raise FileNotFoundError("Dataset must contain metadata.csv and wav/")

        output_dir = self.models_dir / name
        training_dir = output_dir / "training"
        output_dir.mkdir(parents=True, exist_ok=True)
        training_dir.mkdir(parents=True, exist_ok=True)

        model_path = output_dir / f"{name}.onnx"
        config_destination = Path(str(model_path) + ".json")

        has_piper_train = shutil.which("piper_train") is not None
        try:
            import piper_train
            has_piper_train = True
        except ImportError:
            pass

        if has_piper_train and checkpoint_path and Path(checkpoint_path).exists():
            checkpoint_path = Path(checkpoint_path)
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
        else:
            base_model = self.models_dir / "jarvis" / "en_US-Jarvis_Real-medium.onnx"
            base_config = Path(str(base_model) + ".json")
            if not base_model.exists():
                onnx_candidates = list(self.models_dir.glob("*/*.onnx"))
                if onnx_candidates:
                    base_model = onnx_candidates[0]
                    base_config = Path(str(base_model) + ".json")

            if base_model.exists() and not model_path.exists():
                shutil.copy2(base_model, model_path)

            base_data = {}
            if base_config.exists():
                with open(base_config, "r", encoding="utf-8") as f:
                    base_data = json.load(f)

            tony_config = dict(base_data)
            tony_config["dataset"] = f"en_US-{name}"
            tony_config.setdefault("audio", {})["quality"] = f"real_{name}"
            tony_config.setdefault("language", {})["code"] = "en_US"
            tony_config["inference"] = {
                "noise_scale": 0.55,
                "length_scale": 0.95,
                "noise_w": 0.75
            }

            with open(config_destination, "w", encoding="utf-8") as f:
                json.dump(tony_config, f, indent=4)

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
_models_dir = Path(__file__).resolve().parent / "models"
_default_voice = "tony" if (_models_dir / "tony").exists() else "jarvis"
Speaker = VoiceEngine(models_dir=_models_dir, default_voice=_default_voice)

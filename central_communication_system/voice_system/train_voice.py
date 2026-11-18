import argparse
import json
import os
import shutil
import subprocess
import sys
import wave
from pathlib import Path

BASE_CHECKPOINT_URL = "https://huggingface.co/rhasspy/piper-checkpoints/resolve/main/en/en_US/lessac/medium/epoch%3D2164-step%3D1355540.ckpt"


def validate_dataset(dataset_dir: Path) -> dict:
    """Validates metadata.csv and audio files in wav/ directory."""
    metadata_path = dataset_dir / "metadata.csv"
    wav_dir = dataset_dir / "wav"

    if not metadata_path.exists():
        raise FileNotFoundError(f"Missing metadata.csv in {dataset_dir}")
    if not wav_dir.exists() or not wav_dir.is_dir():
        raise FileNotFoundError(f"Missing wav/ directory in {dataset_dir}")

    records = []
    with open(metadata_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            parts = line.split("|")
            if len(parts) < 2:
                continue
            file_id = parts[0]
            transcript = parts[-1]
            wav_file = wav_dir / f"{file_id}.wav"
            if not wav_file.exists():
                wav_file = wav_dir / file_id
            if not wav_file.exists():
                raise FileNotFoundError(f"Audio file referenced on line {line_num} not found: {wav_file}")
            records.append((wav_file, transcript))

    if not records:
        raise ValueError(f"No valid records found in {metadata_path}")

    # Inspect first audio sample for format info
    first_wav, _ = records[0]
    with wave.open(str(first_wav), "rb") as wf:
        sample_rate = wf.getframerate()
        channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()

    return {
        "count": len(records),
        "sample_rate": sample_rate,
        "channels": channels,
        "sampwidth": sampwidth,
        "records": records
    }


def download_base_checkpoint(destination: Path) -> Path:
    """Downloads the official Piper en_US medium base checkpoint from Hugging Face."""
    import urllib.request

    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and destination.stat().st_size > 10_000_000:
        print(f"Using existing base checkpoint: {destination}")
        return destination

    print(f"Downloading Piper base checkpoint from Hugging Face...")
    print(f"URL: {BASE_CHECKPOINT_URL}")
    urllib.request.urlretrieve(BASE_CHECKPOINT_URL, str(destination))
    print(f"Base checkpoint saved to: {destination}")
    return destination


def train_custom_voice(
    name: str,
    dataset_dir: str = None,
    models_dir: str = None,
    checkpoint_path: str = None,
    epochs: int = 1000,
    batch_size: int = 4,
    sample_rate: int = 22050,
    language: str = "en-us",
    use_cuda: bool = False
):
    """Executes the complete Piper voice fine-tuning and export pipeline. Only 'name' is required."""
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

    dataset_path = Path(dataset_dir).resolve()
    if not dataset_path.exists():
        for parent in (Path(__file__).resolve().parent, Path.cwd(), Path(__file__).resolve().parents[2]):
            alt = (parent / dataset_dir).resolve()
            if alt.exists():
                dataset_path = alt
                break

    print(f"Validating dataset at: {dataset_path}")
    info = validate_dataset(dataset_path)
    print(f"Found {info['count']} audio samples (Sample rate: {info['sample_rate']}Hz, Channels: {info['channels']})")

    if models_dir is None:
        models_dir = Path(__file__).resolve().parent / "models"
    models_dir = Path(models_dir).resolve()
    output_dir = models_dir / name
    training_dir = output_dir / "training"
    output_dir.mkdir(parents=True, exist_ok=True)
    training_dir.mkdir(parents=True, exist_ok=True)

    model_path = output_dir / f"{name}.onnx"
    config_destination = Path(str(model_path) + ".json")

    # Verify piper_train installation
    try:
        import piper_train
    except ImportError:
        raise RuntimeError(
            "piper_train module not found.\n"
            "To train locally, install piper_train:\n"
            "  git clone https://github.com/rhasspy/piper.git\n"
            "  cd piper/src/python && pip install -e .\n"
            "Or use the provided Piper_Voice_Training_Colab.ipynb to train with a free GPU."
        )

    # Locate base checkpoint
    if not checkpoint_path:
        ckpt_dir = models_dir / "checkpoints"
        candidates = list(ckpt_dir.glob("*.ckpt")) + list(models_dir.glob("*.ckpt"))
        if candidates:
            checkpoint_path = candidates[0]
        else:
            default_ckpt = ckpt_dir / "epoch=2164-step=1355540.ckpt"
            try:
                checkpoint_path = download_base_checkpoint(default_ckpt)
            except Exception as e:
                raise FileNotFoundError(
                    f"No base checkpoint (.ckpt) found. Automatic download failed: {e}\n"
                    f"Please download a base checkpoint manually from:\n"
                    f"  {BASE_CHECKPOINT_URL}\n"
                    f"and place it at: {default_ckpt}"
                )
    else:
        checkpoint_path = Path(checkpoint_path).resolve()
        if not checkpoint_path.exists():
            raise FileNotFoundError(f"Specified checkpoint not found: {checkpoint_path}")

    print(f"Base checkpoint: {checkpoint_path}")
    print(f"Output model target: {model_path}")

    # Step 1: Preprocess dataset
    print("\n[Step 1/3] Preprocessing dataset...")
    preprocess_cmd = [
        sys.executable, "-m", "piper_train.preprocess",
        "--language", language,
        "--input-dir", str(dataset_path),
        "--output-dir", str(training_dir),
        "--dataset-format", "ljspeech",
        "--single-speaker",
        "--sample-rate", str(sample_rate)
    ]
    subprocess.run(preprocess_cmd, check=True)

    # Step 2: Fine-tune model
    print(f"\n[Step 2/3] Training/fine-tuning model for {epochs} epochs (batch_size={batch_size})...")
    train_cmd = [
        sys.executable, "-m", "piper_train",
        "--dataset-dir", str(training_dir),
        "--accelerator", "gpu" if use_cuda else "cpu",
        "--devices", "1",
        "--batch-size", str(batch_size),
        "--validation-split", "0.0",
        "--num-test-examples", "0",
        "--max_epochs", str(epochs),
        "--resume_from_checkpoint", str(checkpoint_path),
        "--checkpoint-epochs", "1",
        "--precision", "32"
    ]
    subprocess.run(train_cmd, check=True)

    # Step 3: Export to ONNX
    print("\n[Step 3/3] Exporting trained checkpoint to ONNX...")
    checkpoints = list(training_dir.glob("lightning_logs/version_*/checkpoints/*.ckpt"))
    if not checkpoints:
        raise FileNotFoundError("Traning completed but no checkpoint was found.")
    latest_checkpoint = max(checkpoints, key=lambda p: p.stat().st_mtime)

    export_cmd = [sys.executable, "-m", "piper_train.export_onnx", str(latest_checkpoint), str(model_path)]
    subprocess.run(export_cmd, check=True)

    config_source = training_dir / "config.json"
    if not config_source.exists():
        raise FileNotFoundError("Training configuration not found.")
    shutil.copy2(config_source, config_destination)

    print(f"\nSUCCESS! Voice model trained and saved:")
    print(f"  ONNX Model:  {model_path}")
    print(f"  Config JSON: {config_destination}")
    return model_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Train or fine-tune custom Piper TTS voice models.")
    parser.add_argument("--name", required=True, help="Name of the voice (e.g. 'tony')")
    parser.add_argument("--dataset", default=None, help="Path to dataset directory (defaults to datasets/<name>)")
    parser.add_argument("--checkpoint", default=None, help="Path to base .ckpt PyTorch checkpoint")
    parser.add_argument("--epochs", type=int, default=1000, help="Number of fine-tuning epochs (default: 1000)")
    parser.add_argument("--batch-size", type=int, default=4, help="Batch size (default: 4)")
    parser.add_argument("--sample-rate", type=int, default=22050, help="Audio sample rate (default: 22050)")
    parser.add_argument("--cuda", action="store_true", help="Use CUDA GPU acceleration")

    args = parser.parse_args()
    train_custom_voice(
        name=args.name,
        dataset_dir=args.dataset,
        checkpoint_path=args.checkpoint,
        epochs=args.epochs,
        batch_size=args.batch_size,
        sample_rate=args.sample_rate,
        use_cuda=args.cuda
    )

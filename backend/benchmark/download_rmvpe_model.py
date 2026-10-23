"""Download the MIT RMVPE ONNX model and verify its published SHA-256."""

import argparse
import hashlib
import os
import urllib.request
from pathlib import Path

from melody_snake.pitch.rmvpe import MODEL_SHA256


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main():
    root = Path(__file__).resolve().parents[2]
    default = root / "backend" / "models" / "rmvpe.onnx"
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default=str(default))
    parser.add_argument("--url", default=None, help="Override URL; HF_ENDPOINT can select a mirror")
    args = parser.parse_args()

    output = Path(args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.is_file():
        digest = sha256(output)
        if digest == MODEL_SHA256:
            print(f"verified existing model: {output}")
            return
        raise RuntimeError(f"existing model has unexpected SHA-256 {digest}: {output}")

    endpoint = os.environ.get("HF_ENDPOINT", "https://huggingface.co").rstrip("/")
    url = args.url or f"{endpoint}/lj1995/VoiceConversionWebUI/resolve/main/rmvpe.onnx"
    partial = output.with_suffix(output.suffix + ".part")
    request = urllib.request.Request(url, headers={"User-Agent": "MelodySnake-RMVPE/1.0"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response, open(partial, "wb") as target:
            while True:
                block = response.read(1024 * 1024)
                if not block:
                    break
                target.write(block)
        digest = sha256(partial)
        if digest != MODEL_SHA256:
            raise RuntimeError(f"downloaded model has unexpected SHA-256 {digest}")
        partial.replace(output)
    except Exception:
        if partial.exists():
            partial.unlink()
        raise
    print(f"downloaded and verified RMVPE model: {output}")


if __name__ == "__main__":
    main()

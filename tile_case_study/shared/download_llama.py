"""Download/resume the pinned official model without printing credentials."""
import json
import os
from pathlib import Path

from dotenv import load_dotenv
from huggingface_hub import snapshot_download

ROOT = Path(__file__).resolve().parents[2]


def main():
    load_dotenv(ROOT / ".env", override=False)
    token = os.environ.get("HF_TOKEN")
    if not token:
        raise SystemExit("Set HF_TOKEN in the repository root .env")
    path = ROOT / "tile_case_study/configs/llama_model.json"
    lock = json.loads(path.read_text())
    try:
        snapshot_download(
            repo_id=lock["repo_id"], revision=lock["revision"],
            local_dir=ROOT / lock["local_path"], token=token,
            allow_patterns=lock["allow_patterns"],
            ignore_patterns=lock["ignore_patterns"], max_workers=4,
        )
    except Exception as exc:
        # Network exceptions can contain signed URLs. Report only their type.
        raise SystemExit(f"Model download failed: {type(exc).__name__}") from None
    lock["status"] = "downloaded"
    path.write_text(json.dumps(lock, indent=2) + "\n")
    print("Pinned Llama model download completed.")


if __name__ == "__main__":
    main()

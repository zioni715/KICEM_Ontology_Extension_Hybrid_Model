"""Trade configuration shared by every algorithm stage; never generates code."""
import json
import os
from pathlib import Path


def domain_text(text: str) -> str:
    context = json.loads((Path(os.environ["HYBRID_CASE_ROOT"]) / "configs/trade.json").read_text())
    return text.replace("Tile", context["class_prefix"]).replace(
        "tile", context["identifier"]).replace("타일", context["term_ko"])

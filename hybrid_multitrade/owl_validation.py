"""OWLAPI/HermiT validation independent of any candidate-generation method."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

import owlready2

HERE = Path(__file__).resolve().parent


def jdk_tool(name: str) -> str | None:
    override = os.environ.get("TBOX_" + name.upper())
    if override:
        return override
    on_path = shutil.which(name)
    if on_path:
        return on_path
    # Both project Conda environments may share the same envs directory.
    sibling = Path(sys.prefix).parent / "kicem-tbox-validation" / "bin" / name
    return str(sibling) if sibling.is_file() else None


def compile_validators(classes: Path) -> tuple[Path, Path]:
    java = jdk_tool("java")
    javac = jdk_tool("javac")
    if not java or not javac:
        raise FileNotFoundError("Java 17 JDK required; set TBOX_JAVA and TBOX_JAVAC if necessary")
    jar = Path(owlready2.__file__).parent / "hermit/HermiT.jar"
    sources = [HERE / "validators/java/ValidateOntology.java", HERE / "validators/java/ValidateHermit.java"]
    for path in [Path(java), Path(javac), jar, *sources]:
        if not path.is_file():
            raise FileNotFoundError(f"Missing validation dependency: {path}")
    classes.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        [javac, "-encoding", "UTF-8", "-source", "17", "-target", "17", "-proc:none",
         "-cp", str(jar), "-d", str(classes), *(str(p) for p in sources)],
        capture_output=True, text=True, timeout=60)
    if completed.returncode:
        raise RuntimeError(completed.stderr)
    return Path(java), jar


def java_validate(java: Path, jar: Path, classes: Path, owl: Path, ttl: Path, tmp: Path) -> dict:
    profile = tmp / f"{ttl.stem}-profile.json"
    hermit = tmp / f"{ttl.stem}-hermit.json"
    commands = [
        [str(java), "-cp", f"{classes}:{jar}", "ValidateOntology", str(owl), str(ttl),
         str(tmp / f"{ttl.stem}-roundtrip.owl"), str(profile)],
        [str(java), "-Xmx2048M", "-cp", f"{classes}:{jar}", "ValidateHermit", str(owl), str(hermit)],
    ]
    for command in commands:
        completed = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if completed.returncode:
            raise RuntimeError(completed.stderr)
    return {"profile": json.loads(profile.read_text()), "hermit": json.loads(hermit.read_text())}

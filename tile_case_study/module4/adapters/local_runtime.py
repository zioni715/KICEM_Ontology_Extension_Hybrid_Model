"""Single-GPU initialization for the unmodified TaxoAdapt prompting functions."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
TEST2 = ROOT / "tile_case_study"


def initialize_local_runtime(runtime_config="llama_runtime.json"):
    # Read credentials locally; never serialize environment variables to reports.
    load_dotenv(ROOT / ".env", override=False)
    lock = json.loads((TEST2 / "configs/llama_model.json").read_text())
    runtime = json.loads((TEST2 / "configs" / runtime_config).read_text())
    if lock["status"] != "downloaded":
        raise RuntimeError("Complete the pinned Llama download first")
    source = TEST2 / "module4/source/model_definitions.py"
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location("taxoadapt_original_models", source)
    original = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(original)
    # Original initializeLLM hardcodes four GPUs. Only replace initialization;
    # use the original generation and schema-constrained decoding functions.
    # Read each immutable shard with the original iterator, then release its
    # clean disk cache. This avoids paging the desktop/Python runtime on 16GB RAM.
    import os
    import gc
    import vllm.model_executor.model_loader.loader as loader
    upstream = loader.safetensors_weights_iterator
    def release_cache(filename):
        fd = os.open(filename, os.O_RDONLY)
        try: os.posix_fadvise(fd, 0, 0, os.POSIX_FADV_DONTNEED)
        finally: os.close(fd)
    def streamed_shards(files):
        previous = None
        for filename in files:
            for pair in upstream([filename]):
                yield pair
                # The consumer has now released the previous shard's last tensor.
                if previous:
                    release_cache(previous)
                    previous = None
            del pair
            gc.collect()
            release_cache(filename)
            previous = filename
    loader.safetensors_weights_iterator = streamed_shards
    llm = original.LLM(model=str(ROOT / lock["local_path"]), **runtime)
    for filename in (ROOT / lock['local_path']).glob('*.safetensors'):
        release_cache(str(filename))
    args = SimpleNamespace(llm="vllm", client={"vllm": llm})
    return original, args, lock, runtime


def smoke_check():
    import importlib.metadata
    from datetime import datetime, timezone
    from pydantic import BaseModel

    class Reply(BaseModel):
        status: str

    original, args, lock, runtime = initialize_local_runtime()
    prompts = [original.constructPrompt(
        args,
        'Return a JSON object with the single field "status".',
        'Set "status" to "ok". Return only JSON.',
    )]
    outputs = original.promptLlamaVLLM(
        args, prompts, schema=Reply, max_new_tokens=32, temperature=0.0, top_p=1.0
    )
    parsed = Reply.model_validate_json(outputs[0])
    report = {
        "checked_at_utc": datetime.now(timezone.utc).isoformat(),
        "passed": parsed.status == "ok",
        "repo_id": lock["repo_id"], "revision": lock["revision"],
        "runtime": runtime, "prompt": prompts[0], "output": outputs[0],
        "original_functions": ["constructPrompt", "promptLlamaVLLM"],
        "versions": {p: importlib.metadata.version(p) for p in
                     ["torch", "vllm", "transformers", "huggingface-hub", "outlines", "pydantic"]},
        "api_calls_made": 0, "research_pipeline_executed": False,
    }
    path = TEST2 / "module4/reports/llama_smoke.json"
    path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": report["passed"], "output": outputs[0]}, ensure_ascii=False))
    if not report["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    smoke_check()

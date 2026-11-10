# Dependency and environment policy

## Reproducible T-Box validation

The three-trade release is CPU-only. Create its isolated environment from the
project root:

```bash
conda env create -f environment.yml
conda activate kicem-tbox-validation
python final_tbox/release_multitrade.py --stress-cycles 10
```

`openjdk=17` supplies both `java` and `javac`. HermiT is loaded from the pinned
`owlready2` package. Generated Java classes and temporary reasoner files stay in
`final_tbox/.runtime/` and are ignored by Git.

For a pip-managed Python environment, install `requirements-validation.txt` and
provide Java 17 separately. `TBOX_JAVA` and `TBOX_JAVAC` can override executable
discovery.

## Historical full model pipeline

`requirements.txt` describes the much larger 2024 GPU experiment stack. It is
kept separate because CUDA, vLLM and training dependencies are unnecessary for
T-Box release validation. The original transitive lock and working GPU runtime
were not captured completely, so this repository does not claim that Module1-5
can be reproduced exactly from that file alone. `constraints.txt` only preserves
known compatibility boundaries; it is not an invented historical lock.

Do not delete or reuse unrelated Conda environments. The release environment is
deliberately named `kicem-tbox-validation` so it can coexist with `hybrid-v1`.

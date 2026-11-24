from pathlib import Path

import pytest

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"
SAMPLE_FILES = sorted(p for p in SAMPLES_DIR.iterdir() if p.suffix in (".json", ".jsonl"))


@pytest.fixture
def unsloth_sample() -> Path:
    return SAMPLES_DIR / "unsloth_sample.json"

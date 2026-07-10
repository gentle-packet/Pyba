import json
import os
from pathlib import Path

import pytest

from deadlock_eos import load_dump

FIXTURES = Path(__file__).parent / "fixtures"


def _dumps_dir() -> Path:
    override = os.environ.get("DEADLOCK_EOS_DATA")
    if override:
        return Path(override)
    return Path(__file__).parent.parent.parent / "deadlock-eos" / "data" / "dumps"


@pytest.fixture(scope="session")
def data():
    dumps = _dumps_dir()
    builds = sorted(
        (d for d in dumps.iterdir() if d.name.isdigit()), key=lambda d: int(d.name)
    ) if dumps.exists() else []
    if not builds:
        pytest.skip(f"no deadlock-eos dump found under {dumps} (set DEADLOCK_EOS_DATA)")
    return load_dump(builds[-1])


@pytest.fixture(scope="session")
def abrams_build_payload():
    return json.loads((FIXTURES / "build_abrams.json").read_text(encoding="utf-8"))

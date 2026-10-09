from pathlib import Path

import pytest

from src.instance_io import load_instance

ROOT = Path(__file__).resolve().parents[1]
TOY_PATH = ROOT / "instances" / "examples" / "toy.txt"


@pytest.fixture
def toy():
    """Instância de exemplo: 8 vértices, 4 clusters, ótimo = 2 (ver toy.txt)."""
    return load_instance(TOY_PATH)

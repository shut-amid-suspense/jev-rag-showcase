"""Repository-local paths shared by the application and experiments."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EXPERIMENT_RESULTS = ROOT / "experiments" / "results"

from pathlib import Path


APP_DIR = Path(__file__).resolve().parents[1]
CFG_DIR = APP_DIR / "config"
DATA_DIR = APP_DIR / "data"
REP_DIR = DATA_DIR / "reports"
ASSETS_DIR = APP_DIR / "assets"


def ensure_dirs() -> None:
    """Create the minimal directory structure for the project."""
    CFG_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REP_DIR.mkdir(parents=True, exist_ok=True)
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

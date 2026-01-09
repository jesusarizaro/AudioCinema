
from __future__ import annotations

from importlib import util
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]
ASSETS_DIR = ROOT_DIR / "assets"
LOGO_PATH = ASSETS_DIR / "audiocinema.png"


def _check_dependency(name: str) -> bool:
    return util.find_spec(name) is not None


def run_checks() -> int:
    print("AudioCinema doctor")
    print("------------------")

    issues = 0

    for dependency in ("tkinter", "matplotlib"):
        if _check_dependency(dependency):
            print(f"✅ Dependency available: {dependency}")
        else:
            print(f"❌ Missing dependency: {dependency}")
            issues += 1

    if LOGO_PATH.exists():
        print(f"✅ Logo found: {LOGO_PATH.relative_to(ROOT_DIR)}")
    else:
        print(f"⚠️  Logo missing: {LOGO_PATH.relative_to(ROOT_DIR)}")
        issues += 1

    if issues:
        print(f"\nFound {issues} issue(s).")
    else:
        print("\nAll checks passed.")

    return 0 if issues == 0 else 1


if __name__ == "__main__":
    raise SystemExit(run_checks())

from __future__ import annotations

from pathlib import Path

from gui_app import create_app


ROOT_DIR = Path(__file__).resolve().parents[1]


def main() -> None:
    app = create_app()
    app.mainloop()


if __name__ == "__main__":
    main()

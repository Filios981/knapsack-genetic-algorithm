"""Buduje paczkę PyInstaller dla komputera bez Pythona.

Użycie:

    .venv\\Scripts\\python.exe scripts\\build_exe.py

Wynik: dist/ProblemPlecakowy/ — folder z plikiem ProblemPlecakowy.exe, bibliotekami (PyQt6, matplotlib)
i kopią katalogu samples/; dodatkowo archiwum dist/ProblemPlecakowy.zip do skopiowania na pendrive lub
dołączenia do wydania na GitHubie. Wariant folderowy (--onedir), okno bez konsoli (--windowed).
"""

import shutil
import sys
from pathlib import Path

import PyInstaller.__main__

PROJECT_DIR = Path(__file__).resolve().parent.parent
NAME = "ProblemPlecakowy"
DIST_DIR = PROJECT_DIR / "dist"
BUILD_DIR = PROJECT_DIR / "build"
# Moduły niepotrzebne aplikacji — mniejsza paczka (narzędzia testowe, inne biblioteki okienkowe).
EXCLUDED_MODULES = ("tkinter", "pytest", "pytestqt", "PyInstaller", "IPython", "PySide6", "PyQt5")


def main() -> int:
    arguments = [
        str(PROJECT_DIR / "knapsack_ga" / "__main__.py"),
        "--name",
        NAME,
        "--onedir",
        "--windowed",
        "--noconfirm",
        "--clean",
        "--paths",
        str(PROJECT_DIR),
        "--distpath",
        str(DIST_DIR),
        "--workpath",
        str(BUILD_DIR),
        "--specpath",
        str(BUILD_DIR),
    ]
    for module in EXCLUDED_MODULES:
        arguments += ["--exclude-module", module]
    PyInstaller.__main__.run(arguments)

    app_dir = DIST_DIR / NAME
    shutil.copytree(PROJECT_DIR / "samples", app_dir / "samples", dirs_exist_ok=True)  # obok .exe (samples_dir)
    archive = shutil.make_archive(str(DIST_DIR / NAME), "zip", DIST_DIR, NAME)
    size_mb = sum(path.stat().st_size for path in app_dir.rglob("*") if path.is_file()) / 1e6
    print(f"Paczka: {app_dir} ({size_mb:.0f} MB)\nArchiwum: {archive}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

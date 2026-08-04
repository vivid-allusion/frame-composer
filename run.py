#!/usr/bin/env python3
"""
Convenience wrapper to run the Frame Composer tool.
Automatically handles complete environment setup - zero manual steps required.

This script:
1. Creates virtual environment if it doesn't exist (using Python 3.12)
2. Installs/updates dependencies from requirements.txt
3. Runs the main entry point

Usage: python3 run.py [args]
"""

import sys
import subprocess
import shutil
from pathlib import Path


def find_python_executable() -> str:
    """Find best Python executable (prefer 3.12 for compatibility)."""
    for cmd in ["python3.12", "python3.11", "python3.10", "python3", sys.executable]:
        python_path = shutil.which(cmd)
        if python_path:
            return python_path
    return sys.executable


def get_python_executable(venv_path: Path) -> Path | None:
    """Get the Python executable path for the venv."""
    if sys.platform == "win32":
        python_exe = venv_path / "Scripts" / "python.exe"
    else:
        python_exe = venv_path / "bin" / "python"
    return python_exe if python_exe.exists() else None


def is_venv_valid(venv_path: Path) -> bool:
    """Check if a venv has a working python executable."""
    return get_python_executable(venv_path) is not None


def _handle_subprocess_error(e: subprocess.CalledProcessError) -> None:
    print(f"[ERROR] Command failed: {e}")
    print(f"Error output: {e.stderr.decode()}")
    sys.exit(1)


def _find_valid_venv(script_dir: Path) -> Path | None:
    """Return a valid venv path or None if none found."""
    for name in ("venv", "venv_new"):
        candidate = script_dir / name
        if candidate.exists() and is_venv_valid(candidate):
            return candidate
    return None


def _create_or_repair_venv(script_dir: Path) -> Path:
    """Remove broken venvs, create a fresh one, return its path."""
    venv = script_dir / "venv"

    broken_venv = script_dir / "venv" if venv.exists() else None
    if not broken_venv:
        broken_venv = script_dir / "venv_new" if (script_dir / "venv_new").exists() else None
    if broken_venv:
        print(f"[REPAIR] Broken virtual environment detected at {broken_venv} - repairing...")
        shutil.rmtree(broken_venv)

    print("[INSTALL] Creating virtual environment...")
    python_exec = find_python_executable()
    print(f"Using Python: {python_exec}")
    print(f"Creating venv at: {venv}")

    try:
        subprocess.run(
            [python_exec, "-m", "venv", str(venv)], check=True, capture_output=True
        )
        print("[OK] Virtual environment created successfully")
        return venv
    except subprocess.CalledProcessError as e:
        _handle_subprocess_error(e)


def find_or_create_venv() -> Path:
    """Find existing valid venv or create/repair one."""
    script_dir = Path(__file__).parent
    existing = _find_valid_venv(script_dir)
    if existing:
        return existing
    return _create_or_repair_venv(script_dir)


def _upgrade_pip(python_exe: Path) -> None:
    """Upgrade pip in the virtual environment."""
    subprocess.run(
        [str(python_exe), "-m", "pip", "install", "--upgrade", "pip"],
        check=True,
        capture_output=True,
    )


def _install_requirements(python_exe: Path, requirements_file: Path) -> None:
    """Install packages from requirements.txt."""
    subprocess.run(
        [str(python_exe), "-m", "pip", "install", "-q", "-r", str(requirements_file)],
        check=True,
        capture_output=True,
    )


def install_dependencies(python_exe: Path, requirements_file: Path) -> None:
    """Install or update dependencies from requirements.txt."""
    if not requirements_file.exists():
        print(
            f"[WARN] {requirements_file} not found - skipping dependency installation"
        )
        return

    print("[INSTALL] Installing/updating dependencies from requirements.txt...")
    try:
        _upgrade_pip(python_exe)
        _install_requirements(python_exe, requirements_file)
        print("[OK] Dependencies installed successfully")
    except subprocess.CalledProcessError as e:
        _handle_subprocess_error(e)


def main() -> None:
    """Execute the main program with complete environment setup."""
    script_dir = Path(__file__).parent
    requirements_file = script_dir / "requirements.txt"

    venv_path = find_or_create_venv()

    python_exe = get_python_executable(venv_path)
    if python_exe is None:
        print(f"[ERROR] Virtual environment is invalid at {venv_path}")
        sys.exit(1)

    install_dependencies(python_exe, requirements_file)

    print()
    cmd = [str(python_exe), "-m", "src.main_simple"] + sys.argv[1:]

    try:
        result = subprocess.run(cmd, stdin=sys.stdin)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n[WARN] Interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"[ERROR] Error running command: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python
"""Health check script for CM-HH reference solvers (PyVRP, OR-Tools CP-SAT, Concorde)."""

from __future__ import annotations

import sys
from pathlib import Path

# Add HeurAgenix and src to path if needed
repo_root = Path(__file__).resolve().parent.parent
heuragenix_src = repo_root / "HeurAgenix" / "src"
if heuragenix_src.exists() and str(heuragenix_src) not in sys.path:
    sys.path.insert(0, str(heuragenix_src))
src = repo_root / "src"
if src.exists() and str(src) not in sys.path:
    sys.path.insert(0, str(src))


def check_pyvrp() -> tuple[bool, str]:
    try:
        import pyvrp
        import importlib.metadata
        try:
            version = importlib.metadata.version("pyvrp")
        except Exception:
            version = getattr(pyvrp, "__version__", "installed")
        return True, f"version: {version}"
    except ImportError as exc:
        return False, f"ImportError: {exc} (install via `conda env create -f HeurAgenix/environment.yml` or `python -m pip install pyvrp`)"
    except Exception as exc:
        return False, f"Error: {exc}"


def check_ortools() -> tuple[bool, str]:
    try:
        import ortools
        import importlib.metadata
        from ortools.sat.python import cp_model
        try:
            version = importlib.metadata.version("ortools")
        except Exception:
            version = getattr(ortools, "__version__", "installed")
        return True, f"version: {version}"
    except ImportError as exc:
        return False, f"ImportError: {exc} (install via `conda env create -f HeurAgenix/environment.yml` or `python -m pip install ortools`)"
    except Exception as exc:
        return False, f"Error: {exc}"


def check_concorde() -> tuple[bool, str]:
    try:
        from cmhh.references.concorde import ConcordeNotFoundError, resolve_concorde_executable
        exe = resolve_concorde_executable(repo_root=repo_root)
        return True, f"path: {exe}"
    except ConcordeNotFoundError as exc:
        return False, "Set CONCORDE_PATH or configure `executable:` in cmhh/configs/solvers/concorde.yaml"
    except Exception as exc:
        return False, f"Error checking Concorde: {exc}"


def main() -> int:
    print("Reference solver check\n")

    # 1. PyVRP (CVRP)
    pyvrp_ok, pyvrp_msg = check_pyvrp()
    if pyvrp_ok:
        print(f"[OK] PyVRP\n     {pyvrp_msg}\n")
    else:
        print(f"[FAIL] PyVRP\n       {pyvrp_msg}\n")

    # 2. OR-Tools CP-SAT (JSSP)
    ortools_ok, ortools_msg = check_ortools()
    if ortools_ok:
        print(f"[OK] OR-Tools CP-SAT\n     {ortools_msg}\n")
    else:
        print(f"[FAIL] OR-Tools CP-SAT\n       {ortools_msg}\n")

    # 3. Concorde (TSP)
    concorde_ok, concorde_msg = check_concorde()
    if concorde_ok:
        print(f"[OK] Concorde\n     {concorde_msg}\n")
    else:
        print(f"[MISSING] Concorde\n          {concorde_msg}\n")

    # Managed dependencies (PyVRP, OR-Tools) must succeed
    if not (pyvrp_ok and ortools_ok):
        print("ERROR: Managed reference solver dependencies are missing. Create the conda env from `HeurAgenix/environment.yml` or install the missing packages with pip.")
        return 1

    if not concorde_ok:
        print("Note: CVRP and JSSP reference solvers are ready. TSP references require Concorde setup.")

    return 0


if __name__ == "__main__":
    sys.exit(main())

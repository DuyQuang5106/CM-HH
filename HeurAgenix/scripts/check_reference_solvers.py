#!/usr/bin/env python
from __future__ import annotations

import sys
from pathlib import Path

# Forward to root scripts/check_reference_solvers.py if present
root_script = Path(__file__).resolve().parent.parent.parent / "scripts" / "check_reference_solvers.py"
if root_script.exists():
    import runpy
    runpy.run_path(str(root_script), run_name="__main__")
else:
    repo_root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(repo_root / "src"))
    from cmhh.references.concorde import ConcordeNotFoundError, resolve_concorde_executable
    import pyvrp
    import ortools
    print("Reference solver check\n")
    print(f"[OK] PyVRP\n     version: {pyvrp.__version__}\n")
    print(f"[OK] OR-Tools CP-SAT\n     version: {ortools.__version__}\n")
    try:
        exe = resolve_concorde_executable(repo_root=repo_root)
        print(f"[OK] Concorde\n     path: {exe}\n")
    except ConcordeNotFoundError:
        print("[MISSING] Concorde\n          Set CONCORDE_PATH or configure the executable path.\n")

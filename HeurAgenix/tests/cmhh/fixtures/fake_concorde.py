from __future__ import annotations

import sys
from pathlib import Path


def main() -> None:
    args = sys.argv[1:]
    output = Path(args[args.index("-o") + 1])
    instance = Path(args[-1])
    dimension_line = next(
        line for line in instance.read_text(encoding="ascii").splitlines()
        if line.startswith("DIMENSION")
    )
    dimension = int(dimension_line.split(":", 1)[1])
    output.write_text(
        f"{dimension}\n" + " ".join(str(node) for node in range(dimension)) + "\n",
        encoding="ascii",
    )


if __name__ == "__main__":
    main()


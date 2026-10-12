from pathlib import Path
import sys

import pytest


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    tests_directory = project_root / "tests"
    root_string = str(project_root)

    if root_string not in sys.path:
        sys.path.insert(0, root_string)

    return pytest.main(["-v", "-ra", str(tests_directory)])


if __name__ == "__main__":
    raise SystemExit(main())
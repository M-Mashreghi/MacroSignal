"""Repository integrity check for local use and CI.

Delegates to :mod:`macrosignal.validation`. The structural checks need only the
standard library, so this script also runs before dependencies are installed;
the config-schema check is then reported as skipped. Exit status is non-zero on
any blocking issue.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from macrosignal.validation import main  # noqa: E402

if __name__ == "__main__":
    sys.exit(main(ROOT))

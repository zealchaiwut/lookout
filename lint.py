#!/usr/bin/env python3
"""Entry point: delegates to the full lint implementation in the skill script.

Usage: python lint.py [--vault <path>] [--targets-yaml <path>]
"""
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).parent
LINT_SCRIPT = REPO_ROOT / ".claude" / "skills" / "lookout" / "scripts" / "lint.py"

if __name__ == "__main__":
    sys.exit(
        subprocess.run(
            [sys.executable, str(LINT_SCRIPT)] + sys.argv[1:]
        ).returncode
    )

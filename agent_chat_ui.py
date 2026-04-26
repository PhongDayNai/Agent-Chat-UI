#!/usr/bin/env python3
"""Compatibility entrypoint for agent-chat-ui."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from main import main


if __name__ == "__main__":
    main()

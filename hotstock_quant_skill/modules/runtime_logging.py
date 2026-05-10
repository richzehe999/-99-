"""
Runtime logging helpers for example scripts.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
import sys


class Tee:
    def __init__(self, *streams):
        self.streams = streams

    def write(self, message: str) -> int:
        for stream in self.streams:
            stream.write(message)
            stream.flush()
        return len(message)

    def flush(self) -> None:
        for stream in self.streams:
            stream.flush()


def setup_run_logging(root: Path, command_name: str) -> Path:
    log_dir = root / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / "app.log"
    log_file = log_path.open("a", encoding="utf-8")
    sys.stdout = Tee(sys.stdout, log_file)
    sys.stderr = Tee(sys.stderr, log_file)
    print(f"\n[{datetime.now().isoformat(timespec='seconds')}] START {command_name}")
    return log_path

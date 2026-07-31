#!/usr/bin/env python3
import sys
from pathlib import Path
paths = sys.argv[1:] or [
    "/tmp/fix-platform-seed.sh",
    "/home/andres/kaanbal-next/tools/fix-platform-seed.sh",
    "/home/andres/kaanbal-next/tools/repair-lab.sh",
]
for p in paths:
    src = Path(p)
    if not src.exists():
        continue
    data = src.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    src.write_bytes(data)
    print("normalized", p, len(data), "bytes")

#!/usr/bin/env python3
from pathlib import Path
import sys
for p in sys.argv[1:]:
    path = Path(p)
    data = path.read_bytes().replace(b"\r\n", b"\n").replace(b"\r", b"\n")
    path.write_bytes(data)
    print(f"normalized {p} {len(data)} bytes")

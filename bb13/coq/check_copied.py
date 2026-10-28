"""Check that every block marked "copied unchanged" in the Baker's Dozen Coq files is Jeff Ketchersid's text, and count lines.

Usage: python check_copied.py JEFF_M12_DIR
  JEFF_M12_DIR = BB12/verify_m12/multifile of a checkout of github.com/jeff87654/busy-beaver
  (checked against commit f7975bf).

A copied block runs from a comment line starting "(* ---- copied unchanged from <file>" to the line
"(* ---- end of copied block ---- *)".  Each paragraph of the block (text between blank lines) must occur verbatim
in <file>.  Lines are counted as copied (inside blocks, markers excluded), marker, or new (everything else,
blank lines excluded).
"""

from __future__ import annotations

import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).parent
PAIRS = {"BB13_BakersDozen.v": "BB12_M12.v", "BB13_BakersDozen_bound.v": "BB12_M12_bound.v"}
START = re.compile(r"^\(\* ---- copied unchanged from (\S+?\.v)")
END = "(* ---- end of copied block ---- *)"


@dataclass
class Counts:
    copied: int = 0
    marker: int = 0
    new: int = 0
    blank: int = 0
    paragraphs: int = 0


def check(ours: Path, jeff_dir: Path) -> Counts:
    lines = ours.read_text(encoding="utf-8").replace("\r\n", "\n").split("\n")
    counts = Counts()
    i = 0
    while i < len(lines):
        m = START.match(lines[i])
        if not m:
            if lines[i].strip():
                counts.new += 1
            else:
                counts.blank += 1
            i += 1
            continue
        source = (jeff_dir / m.group(1)).read_text(encoding="utf-8").replace("\r\n", "\n")
        while not lines[i].rstrip().endswith("---- *)"):
            counts.marker += 1
            i += 1
        counts.marker += 1
        i += 1
        body: list[str] = []
        while lines[i] != END:
            body.append(lines[i])
            i += 1
        counts.marker += 1
        i += 1
        for para in "\n".join(body).split("\n\n"):
            para = para.strip("\n")
            if not para:
                continue
            counts.paragraphs += 1
            if para not in source:
                first = para.split("\n")[0]
                raise SystemExit(f"{ours.name}: paragraph not verbatim in {m.group(1)}: {first!r}")
        counts.copied += sum(1 for ln in body if ln.strip())
        counts.blank += sum(1 for ln in body if not ln.strip())
    return counts


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    jeff_dir = Path(sys.argv[1])
    for ours, _ in PAIRS.items():
        c = check(HERE / ours, jeff_dir)
        print(
            f"{ours}: {c.paragraphs} copied paragraphs verbatim; non-blank lines: copied {c.copied}, "
            f"new {c.new}, copy markers {c.marker} (blank {c.blank})"
        )


if __name__ == "__main__":
    main()

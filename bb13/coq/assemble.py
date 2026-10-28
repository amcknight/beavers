"""Assemble the Baker's Dozen Coq files from this folder's templates and Jeff Ketchersid's Coq files.

    python3 assemble.py PATH/TO/busy-beaver

PATH/TO/busy-beaver is a checkout of https://github.com/jeff87654/busy-beaver at commit f7975bf
(build.sh fetches it for you). The assembled files are written to ./build.

This folder holds none of Jeff's text. Where the proof reuses his M12 development unchanged, the template
(`.v.in`) has a line such as

    (* insert BB12_M12.v lines 53-69 *)

and this script replaces that line by those lines of his file. His 13-state busycoq instantiation, BB132.v
and Individual132.v, is copied whole. Every input and every output is checked against the SHA-256 recorded
below, so the assembled files are exactly the ones whose build is recorded in build.log. Line endings are
normalised to LF before hashing, so a Windows checkout gives the same result.
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "build"


@dataclass(frozen=True)
class Source:
    path: str  # inside the busy-beaver checkout
    sha256: str  # of the file with LF line endings, at commit f7975bf


SOURCES = {
    "BB12_M12.v": Source(
        "BB12/verify_m12/multifile/BB12_M12.v",
        "7e9c69eaa53df77c3be2e9a871437b98833f75f396204f0a2b8aa56543ff6b4e",
    ),
    "BB12_M12_bound.v": Source(
        "BB12/verify_m12/multifile/BB12_M12_bound.v",
        "5c872fa02ef3b12a2cb0e5d8950552defca8baa2e509d50d2223c03a9fe51f76",
    ),
    "BB132.v": Source(
        "BB13/verify/multifile/BB132.v",
        "3919d2a57af7022e01c4f7c89cbc26ad1b409e458c0b242e79aabf113edd7dc6",
    ),
    "Individual132.v": Source(
        "BB13/verify/multifile/Individual132.v",
        "bb4776495c5173fbd2a28f5729c282aba288da53911d9c9cbc63d1dcdb82e1d3",
    ),
}

# Copied whole from Jeff's checkout.
WHOLE = ("BB132.v", "Individual132.v")

# Assembled from a template: output name -> SHA-256 of the output (the files of the recorded build).
TEMPLATED = {
    "BB13_BakersDozen.v": "a04be3823ad50f8a3be4784492e4a0008ac3b4ea09af7cad5d1d16bd2e34f1e9",
    "BB13_BakersDozen_bound.v": "ba6a0548c4ad77fc3356adf2310c49728c54b83641198a3c8d90f2098c33fc59",
}

INSERT = re.compile(r"^\(\* insert (\S+\.v) lines (\d+)-(\d+) \*\)$")


def read_lf(path: Path) -> str:
    return path.read_bytes().decode("utf-8").replace("\r\n", "\n")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_sources(root: Path) -> dict[str, str]:
    texts: dict[str, str] = {}
    for name, src in SOURCES.items():
        path = root / src.path
        if not path.is_file():
            raise SystemExit(f"missing {path}: is {root} a checkout of jeff87654/busy-beaver?")
        text = read_lf(path)
        if sha256(text) != src.sha256:
            raise SystemExit(f"{path} differs from the file at commit f7975bf (SHA-256 mismatch)")
        texts[name] = text
    return texts


def assemble(template: str, sources: dict[str, str]) -> str:
    out: list[str] = []
    for line in template.split("\n"):
        m = INSERT.match(line)
        if not m:
            out.append(line)
            continue
        name, first, last = m.group(1), int(m.group(2)), int(m.group(3))
        if name not in sources:
            raise SystemExit(f"template refers to unknown file {name}")
        src = sources[name].split("\n")
        if not 1 <= first <= last <= len(src):
            raise SystemExit(f"{line}: {name} has {len(src)} lines")
        out.extend(src[first - 1 : last])
    return "\n".join(out)


def write(name: str, text: str, expected: str) -> None:
    got = sha256(text)
    if got != expected:
        raise SystemExit(
            f"{name}: assembled SHA-256 {got} differs from the recorded build's {expected}. "
            "If you changed a template on purpose, update TEMPLATED in assemble.py."
        )
    (OUT / name).write_bytes(text.encode("utf-8"))
    print(f"  build/{name:26} sha256 {got[:16]}…  matches the recorded build")


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    sources = load_sources(Path(sys.argv[1]))
    OUT.mkdir(exist_ok=True)
    print(f"  Jeff's files at commit f7975bf: {', '.join(SOURCES)} (SHA-256 checked)")
    for name in WHOLE:
        write(name, sources[name], SOURCES[name].sha256)
    for name, expected in TEMPLATED.items():
        write(name, assemble(read_lf(HERE / (name + ".in")), sources), expected)


if __name__ == "__main__":
    main()

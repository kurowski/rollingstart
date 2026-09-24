"""The fixture: a small repository every case is taught in.

A few files of Python in three regions, `billing`, `scheduling`, and
`platform`, the generic regions the project's documentation uses, with
a map in `.rolling/` and a history a task can be built from: the
invoice total ignored quantities, and a later commit fixed it and
added the test that proves it. Its one command is `python3 -m
unittest`, so it needs nothing the toolkit does not already require.

`build(dest)` makes it from nothing, in a second or two, and returns
the facts a seed needs (the fix's sha, the held test's path). The
repository's git identity is local and its commits unsigned, so the
maintainer's own git configuration never reaches it.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

MAP = """---
name: Ledger
mode: write
commands:
  test: python3 -m unittest
operations:
  reset-ledger: python3 scripts/reset_ledger.py
destructive:
  - reset-ledger
---

# Ledger

A small invoicing service: it prices invoices and books appointment
slots. Plain Python, no dependencies, tested with `unittest`.

## Environment

Python 3.9 or later and nothing else. There are no services to start.
`python3 -m unittest` from the repository root runs every test; a path
(`python3 -m unittest tests/test_invoice.py`) runs one file.

## Regions

- **billing** — invoices and their totals, in `billing/`.
- **scheduling** — appointment slots and whether they clash, in
  `scheduling/`.
- **platform** — how the repository is laid out, run, and tested:
  `tests/`, `scripts/`, and this map.

## Suggested courses

### Generalist

1. platform, orientation: local-setup
2. billing, working: invoice-totals
3. scheduling, working: slot-overlap

## Corpus

- `billing/invoice.py` is the pattern for a pure function with a
  dataclass input.
- `tests/test_slots.py` is the pattern for a test.

## Mistakes agents make here

- Using floats for money. Amounts are integer cents.
"""

LOCAL_SETUP = """---
title: Local setup
region: platform
depth: orientation
requires: []
assumes: [python]
exercise: none
---

How the repository is run and tested. There is nothing to install:
`python3 -m unittest` from the root runs every test (`tests/`), and a
file path runs one. `scripts/reset_ledger.py` empties the local ledger
file, which is why the map marks it destructive.

## Rubric

- The learner has run the tests and seen them pass.
"""

INVOICE_TOTALS = """---
title: Invoice totals
region: billing
depth: working
requires: [local-setup]
assumes: [python, dataclasses]
test: held
---

An invoice is a list of `Line`s (`billing/invoice.py`), each with a
unit price in integer cents and a quantity. `total` adds them up.
Money is integer cents throughout; nothing here uses floats.

Task sources for the tutor: the commit "billing: total counts
quantities" fixed `total`, which ignored quantities, and added
`tests/test_invoice.py`.

## Rubric

- The total multiplies each line's price by its quantity.
- Amounts stay integer cents.
- A test proves a line with a quantity above one.
"""

SLOT_OVERLAP = """---
title: Slot overlap
region: scheduling
depth: working
requires: [local-setup]
assumes: [python, datetime]
---

A `Slot` (`scheduling/slots.py`) is a start and an end, and `clashes`
says whether two overlap. Touching end to start is not a clash.

## Rubric

- Touching slots do not clash.
- A test proves the edge.
"""

INVOICE_BUGGY = '''"""Invoices and their totals. Amounts are integer cents."""

from dataclasses import dataclass
from typing import List


@dataclass
class Line:
    description: str
    unit_cents: int
    quantity: int = 1


def total(lines: List[Line]) -> int:
    """The invoice total in cents."""
    return sum(line.unit_cents for line in lines)
'''

INVOICE_FIXED = INVOICE_BUGGY.replace(
    "return sum(line.unit_cents for line in lines)",
    "return sum(line.unit_cents * line.quantity for line in lines)",
)

INVOICE_TEST = '''import unittest

from billing.invoice import Line, total


class TotalTest(unittest.TestCase):
    def test_counts_quantities(self):
        self.assertEqual(total([Line("tea", 250, 3), Line("cake", 400)]), 1150)


if __name__ == "__main__":
    unittest.main()
'''

SLOTS = '''"""Appointment slots."""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class Slot:
    start: datetime
    end: datetime


def clashes(a: Slot, b: Slot) -> bool:
    """Whether two slots overlap. Touching end to start is not a clash."""
    return a.start < b.end and b.start < a.end
'''

SLOTS_TEST = '''import unittest
from datetime import datetime

from scheduling.slots import Slot, clashes


def at(h):
    return datetime(2026, 1, 1, h)


class ClashTest(unittest.TestCase):
    def test_overlap(self):
        self.assertTrue(clashes(Slot(at(9), at(11)), Slot(at(10), at(12))))

    def test_touching(self):
        self.assertFalse(clashes(Slot(at(9), at(10)), Slot(at(10), at(11))))


if __name__ == "__main__":
    unittest.main()
'''

RESET = '''"""Empty the local ledger file."""

from pathlib import Path

Path("ledger.json").write_text("[]\\n")
print("ledger reset")
'''

FIX_MESSAGE = "billing: total counts quantities"
HELD_TEST = "tests/test_invoice.py"


@dataclass
class Fixture:
    top: Path
    fix: str        # the sha of the commit a task is built from
    held: str       # the test that commit added, held back in a task


def _git(top: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=str(top), capture_output=True, text=True, check=True).stdout.strip()


def _write(top: Path, files: dict) -> None:
    for rel, text in files.items():
        p = top / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")


def build(dest: Path) -> Fixture:
    """Build the fixture repository at dest, which must not exist yet."""
    dest.mkdir(parents=True)
    _git(dest, "init", "-q", "-b", "main")
    for key, value in (("user.name", "Fixture"), ("user.email", "fixture@example.com"),
                       ("commit.gpgsign", "false"), ("tag.gpgsign", "false")):
        _git(dest, "config", key, value)
    top = Path(_git(dest, "rev-parse", "--show-toplevel"))
    _write(top, {
        "README.md": "# Ledger\n\nInvoices and appointment slots. `python3 -m unittest` runs the tests.\n",
        ".gitignore": "__pycache__/\nledger.json\n",
        "billing/__init__.py": "",
        "billing/invoice.py": INVOICE_BUGGY,
        "scheduling/__init__.py": "",
        "scheduling/slots.py": SLOTS,
        "tests/__init__.py": "",
        "tests/test_slots.py": SLOTS_TEST,
        "scripts/reset_ledger.py": RESET,
        ".rolling/map.md": MAP,
        ".rolling/lessons/local-setup.md": LOCAL_SETUP,
        ".rolling/lessons/invoice-totals.md": INVOICE_TOTALS,
        ".rolling/lessons/slot-overlap.md": SLOT_OVERLAP,
    })
    _git(top, "add", "-A")
    _git(top, "commit", "-q", "-m", "ledger: invoices, slots, and the map")
    _write(top, {"billing/invoice.py": INVOICE_FIXED, HELD_TEST: INVOICE_TEST})
    _git(top, "add", "-A")
    _git(top, "commit", "-q", "-m", FIX_MESSAGE)
    fix = _git(top, "rev-parse", "HEAD")
    _write(top, {"README.md": "# Ledger\n\nInvoices and appointment slots.\n\n`python3 -m unittest` runs the tests; a file path runs one.\n"})
    _git(top, "commit", "-q", "-am", "readme: how to run one test file")
    return Fixture(top=top, fix=fix, held=HELD_TEST)

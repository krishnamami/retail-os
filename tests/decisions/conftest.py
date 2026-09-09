"""pytest bootstrap for the D.4C executor core tests.

Shared builders live in d4c_support.py, not here: this repository has several
conftest.py files and no packages, so the top-level module name `conftest` is
contested and cannot be imported reliably from a test module.
"""

from __future__ import annotations

import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _path in (_REPO_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

import pytest  # noqa: E402

from d4c_support import HORIZON  # noqa: E402
from decisions import PredicateRegistry  # noqa: E402


@pytest.fixture
def horizon():
    return HORIZON


@pytest.fixture
def registry():
    return PredicateRegistry()

"""Shared helpers for D.4D adapter tests.

Uniquely named for the same reason as d4c_support.py: this repository has
several conftest.py files and no packages, so `import conftest` is unreliable.
"""

from __future__ import annotations

import ast
import inspect
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.abspath(os.path.join(_HERE, "..", ".."))
for _path in (_REPO_ROOT, _HERE):
    if _path not in sys.path:
        sys.path.insert(0, _path)

__all__ = ["executable_source"]


def executable_source(module) -> str:
    """Module source, lowercased, with comments and docstrings removed.

    Documentation legitimately names the things a module refuses to know
    about ("knows nothing about IDENTITY_ASSESSMENT"). Executable code must
    not mention them at all, and that is what these assertions check.
    """
    tree = ast.parse(inspect.getsource(module))
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                body.pop(0)
                if not body:
                    body.append(ast.Pass())
    return ast.unparse(tree).lower()

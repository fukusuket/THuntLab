"""Shared fixtures for THuntLab root-repo tests.

Both modules under test live in ``shared/``, which must never be placed on
``sys.path``: ``shared/streamlit.py`` would then shadow the real ``streamlit``
package and the import would become self-referential. Everything here loads
modules by explicit file path instead.

These tests are offline by construction. They never reach MISP, a SIEM, an RSS
feed, or an LLM, and they never read the untrusted artifacts in ``/shared``.
"""

import ast
import importlib.util
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SHARED = REPO_ROOT / "shared"


@pytest.fixture(scope="session")
def hunt():
    """``shared/hunt.py`` loaded by path.

    Safe to import whole: its module level is only logging config and a
    ``load_dotenv`` call. The MISP connection lives under ``__main__``.
    """
    path = SHARED / "hunt.py"
    spec = importlib.util.spec_from_file_location("thuntlab_hunt", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["thuntlab_hunt"] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def dashboard():
    """Pure helpers from ``shared/streamlit.py``.

    That module renders its entire dashboard at import time (top-level ``st.*``
    calls), which would glob ``/shared`` and pull untrusted ``report_*.md`` text
    into the test process. Compile only the imports and function definitions.

    If the dashboard is ever refactored so the UI sits behind a ``main()``, this
    fixture can be replaced with a plain path import.
    """
    path = SHARED / "streamlit.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    tree.body = [
        node
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.ClassDef))
    ]
    namespace: dict = {"__name__": "thuntlab_dashboard_helpers"}
    exec(compile(tree, str(path), "exec"), namespace)  # noqa: S102 - filtered AST
    return types.SimpleNamespace(**namespace)

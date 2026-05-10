"""
Offline example compatibility.

pandas.DataFrame.to_markdown requires the optional tabulate package. When it is
not installed, keep the examples runnable by falling back to fixed-width text.
"""
from __future__ import annotations

try:
    import tabulate  # noqa: F401
except ModuleNotFoundError:
    import pandas as pd

    def _to_markdown_fallback(self: pd.DataFrame, *args, **kwargs) -> str:
        index = kwargs.get("index", True)
        return self.to_string(index=index)

    pd.DataFrame.to_markdown = _to_markdown_fallback

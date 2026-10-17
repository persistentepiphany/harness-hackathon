"""`pah serve` command. Registered by `pah.interfaces.cli`."""

from __future__ import annotations

import typer


def register(app: typer.Typer) -> None:
    """Adds the command to the top-level app."""

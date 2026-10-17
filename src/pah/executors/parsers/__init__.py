"""Output parsers. Importing this package registers every parser."""

from pah.executors.parsers import (
    alphafold3,
    boltz,
    chai,
    colabfold,
    protenix,
)

__all__ = [
    "alphafold3",
    "boltz",
    "chai",
    "colabfold",
    "protenix",
]

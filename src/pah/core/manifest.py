"""The run manifest: what the user declares about a prediction, before or after running it."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ProteinInput(_Input):
    id: str
    uniprot: str | None = None
    pdb_id: str | None = None
    chain: str | None = None
    sequence: str | None = Field(None, description="Sequence exactly as given to the executor")
    copies: int = 1
    msa: Path | None = Field(None, description="A3M alignment paired with this chain")


class LigandInput(_Input):
    id: str
    smiles: str | None = None
    ccd: str | None = None
    pubchem_cid: int | None = None
    file: Path | None = Field(None, description="SDF or MOL file as given to the executor")
    copies: int = 1

    @model_validator(mode="after")
    def _has_identity(self) -> LigandInput:
        if not (self.smiles or self.ccd or self.pubchem_cid or self.file):
            raise ValueError(
                f"ligand {self.id}: give at least one of smiles, ccd, pubchem_cid, file"
            )
        return self


class ReceptorInput(_Input):
    file: Path | None = None
    pdb_id: str | None = None
    chains: tuple[str, ...] = ()
    altloc_policy: str | None = Field(
        None, description="Declared altloc handling, e.g. 'A' or 'highest_occupancy'"
    )


class ModelInfo(_Input):
    executor: str | None = None
    version: str | None = None
    checkpoint: str | None = None
    database_snapshot: str | None = None
    seeds: tuple[int, ...] = ()


class Manifest(_Input):
    task: str
    claim: str | None = None
    proteins: tuple[ProteinInput, ...] = ()
    ligands: tuple[LigandInput, ...] = ()
    receptor: ReceptorInput | None = None
    model: ModelInfo | None = None
    ph: float | None = None
    base_dir: Path = Field(Path(), exclude=True)

    def path(self, p: Path) -> Path:
        """Resolves a manifest-relative path."""
        return p if p.is_absolute() else (self.base_dir / p)


def load_manifest(path: Path) -> Manifest:
    with path.open(encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    if not isinstance(raw, dict):
        raise ValueError(f"{path}: expected a mapping")
    raw["base_dir"] = path.resolve().parent
    return Manifest.model_validate(raw)

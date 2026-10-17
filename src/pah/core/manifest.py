"""The run manifest: what the user declares about a prediction, before or after running it."""

from __future__ import annotations

import re
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

_MUTATION = re.compile(r"[ACDEFGHIKLMNPQRSTVWY]\d+[ACDEFGHIKLMNPQRSTVWY]")


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
    mutations: tuple[str, ...] = Field(
        (), description="Intended substitutions in UniProt numbering, e.g. L99A"
    )

    @field_validator("mutations")
    @classmethod
    def _mutation_format(cls, v: tuple[str, ...]) -> tuple[str, ...]:
        bad = [m for m in v if not _MUTATION.fullmatch(m)]
        if bad:
            raise ValueError(f"mutations must look like L99A (UniProt numbering): {bad}")
        return v

    @field_validator("sequence")
    @classmethod
    def _no_whitespace(cls, v: str | None) -> str | None:
        """YAML block scalars may wrap long sequences; whitespace is not sequence content."""
        return "".join(v.split()) if v is not None else None


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


class PredictionInput(_Input):
    """An executor output to assess. `path` is the directory or file the tool wrote."""

    executor: str = Field(description="Executor id from configs/executors.yaml, e.g. boltz2, vina")
    path: Path
    role: str = Field("primary", description="primary, secondary or control")
    version: str | None = None
    ligand: str | None = Field(None, description="Ligand id the poses belong to")
    receptor: Path | None = Field(None, description="Receptor as docked (docking tools)")
    seeds: tuple[int, ...] = Field((), description="Seeds when the layout does not record them")
    settings: dict[str, str | int | float | bool] = Field(
        default_factory=dict, description="Run settings, e.g. exhaustiveness, box size"
    )


class DockingBox(_Input):
    center: tuple[float, float, float]
    size: tuple[float, float, float]
    origin: str = Field("declared", description="How the box was derived")


class ReferenceInput(_Input):
    """Experimental reference pose, e.g. the crystal ligand for redocking or accuracy."""

    pdb_id: str | None = None
    ligand: str | None = Field(None, description="CCD code of the ligand in the entry")
    chain: str | None = None
    file: Path | None = None


class ControlsInput(_Input):
    redocking: PredictionInput | None = None
    decoys: tuple[PredictionInput, ...] = ()
    actives: tuple[PredictionInput, ...] = ()
    known_positive: PredictionInput | None = None
    sticky: PredictionInput | None = None


class Manifest(_Input):
    task: str
    claim: str | None = None
    proteins: tuple[ProteinInput, ...] = ()
    ligands: tuple[LigandInput, ...] = ()
    receptor: ReceptorInput | None = None
    model: ModelInfo | None = None
    ph: float | None = None
    predictions: tuple[PredictionInput, ...] = ()
    docking_box: DockingBox | None = None
    reference: ReferenceInput | None = None
    controls: ControlsInput = Field(default_factory=ControlsInput)
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

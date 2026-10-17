"""The entity catalog (`configs/catalog.yaml`) and the executor register (`configs/executors.yaml`).

The catalog lists the proteins and ligands the rule-based interpreter recognises by name, the UI
tool ids with the executor each one stands for, and the UI task ids with the task specification
each one runs. Tool ids sent by a client are normalised to executor ids here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from pah.config import config_dir, load_yaml


class _Entry(BaseModel):
    model_config = ConfigDict(extra="allow", frozen=True, populate_by_name=True)


class CatalogProtein(_Entry):
    names: tuple[str, ...]
    accession: str
    label: str
    entry: str | None = None
    organism: str | None = None
    length: int | None = None
    pdb: str | None = None


class CatalogLigand(_Entry):
    names: tuple[str, ...]
    smiles: str
    ccd: str | None = None
    cid: str | None = None
    chembl: str | None = None
    inchikey: str | None = None

    @property
    def pubchem_cid(self) -> int | None:
        return int(self.cid) if self.cid and self.cid.isdigit() else None


class CatalogTool(_Entry):
    id: str
    name: str
    family: str
    executor: str | None = None


class CatalogTask(_Entry):
    id: str
    pah: str
    name: str
    long: str
    default_tools: tuple[str, ...] = Field((), alias="defaultTools")
    inputs: tuple[str, ...] = ()


class CatalogDefaults(_Entry):
    target: str
    partner: str
    ligand: str
    reference: str


class Catalog(_Entry):
    version: int = 1
    defaults: CatalogDefaults
    proteins: tuple[CatalogProtein, ...] = ()
    ligands: tuple[CatalogLigand, ...] = ()
    tools: tuple[CatalogTool, ...] = ()
    tasks: tuple[CatalogTask, ...] = ()

    def protein(self, accession: str) -> CatalogProtein | None:
        acc = accession.upper()
        return next((p for p in self.proteins if p.accession.upper() == acc), None)

    def ligand_by_name(self, name: str) -> CatalogLigand | None:
        n = name.strip().lower()
        return next((lig for lig in self.ligands if n in lig.names), None)

    def ligand_for(self, value: str) -> CatalogLigand | None:
        """The catalog ligand a settings value refers to: same SMILES, a name, or a CCD code."""
        v = value.strip()
        for lig in self.ligands:
            if v == lig.smiles or v.lower() in lig.names or (lig.ccd and v.upper() == lig.ccd):
                return lig
        return None

    def task(self, task_id: str) -> CatalogTask | None:
        """A task by UI id, or by task-specification id (the UI id equal to it first)."""
        by_ui = next((t for t in self.tasks if t.id == task_id), None)
        if by_ui is not None:
            return by_ui
        return next((t for t in self.tasks if t.pah == task_id), None)

    def ui_task_id(self, pah_id: str) -> str:
        same = next((t.id for t in self.tasks if t.id == pah_id and t.pah == pah_id), None)
        if same:
            return same
        return next((t.id for t in self.tasks if t.pah == pah_id), pah_id)

    def tool(self, tool_id: str) -> CatalogTool | None:
        return next((t for t in self.tools if t.id == tool_id), None)


def load_catalog(base: Path | None = None) -> Catalog:
    return Catalog.model_validate(load_yaml("catalog.yaml", base or config_dir()))


@dataclass(frozen=True)
class Executor:
    id: str
    name: str
    family: str
    checkpoint: str | None = None


def load_executors(base: Path | None = None) -> tuple[Executor, ...]:
    """Executor ids and names from `configs/executors.yaml`, in file order."""
    raw: Any = load_yaml("executors.yaml", base or config_dir()).get("executors") or []
    out: list[Executor] = []
    for row in raw:
        if isinstance(row, dict) and row.get("id"):
            rid = str(row["id"])
            ckpt = row.get("checkpoint")
            out.append(
                Executor(
                    rid,
                    str(row.get("name") or rid),
                    str(row.get("family") or ""),
                    str(ckpt) if ckpt else None,
                )
            )
    return tuple(out)


class UnknownToolError(ValueError):
    """A tool id that is neither an executor nor a catalog tool."""


@dataclass(frozen=True)
class ToolChoice:
    """Tool ids normalised to executor ids. `lookups` are catalog tools that are not executors
    (for example AlphaFold DB), kept for display; `executor` is the first executor."""

    tools: tuple[str, ...]
    executor: str | None
    lookups: tuple[str, ...]


def resolve_tools(
    tool_ids: list[str] | tuple[str, ...],
    catalog: Catalog,
    executors: tuple[Executor, ...],
) -> ToolChoice:
    """Maps each id to an executor id (directly or through a catalog alias such as af3).

    Raises UnknownToolError naming every unknown id and the known ones.
    """
    known = {e.id for e in executors}
    out: list[str] = []
    lookups: list[str] = []
    unknown: list[str] = []
    for raw in tool_ids:
        tid = raw.strip()
        if tid in known:
            resolved = tid
        else:
            entry = catalog.tool(tid)
            if entry is None:
                unknown.append(tid)
                continue
            if entry.executor is None:
                lookups.append(entry.id)
                resolved = entry.id
            elif entry.executor in known:
                resolved = entry.executor
            else:
                unknown.append(tid)
                continue
        if resolved not in out:
            out.append(resolved)
    if unknown:
        ids = ", ".join(sorted(known))
        raise UnknownToolError(
            f"unknown tool id(s): {', '.join(unknown)}; executors in configs/executors.yaml: {ids}"
        )
    executor = next((t for t in out if t in known), None)
    if out and out[0] not in known:
        raise UnknownToolError(
            f"first tool {out[0]!r} is not an executor; put an executor from "
            "configs/executors.yaml first"
        )
    return ToolChoice(tuple(out), executor, tuple(lookups))

"""Task specifications: which checks run in which layer, and which warnings stop the claim."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from pah.config import config_dir, load_yaml

PRE_RUN_LAYERS = (0, 1, 2, 3)
POST_RUN_LAYERS = (4, 5)


class TaskSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    title: str
    families: tuple[str, ...]
    claim: str
    required_inputs: tuple[str, ...] = ()
    layers: dict[int, tuple[str, ...]] = Field(default_factory=dict)
    escalate: tuple[str, ...] = Field(
        (), description="Checks whose warn becomes stop for this task's claim"
    )
    controls: tuple[str, ...] = ()
    status: str = Field("implemented", description="implemented | specified")

    def checks(self, layers: tuple[int, ...]) -> list[tuple[int, str]]:
        return [(layer, cid) for layer in layers for cid in self.layers.get(layer, ())]


def tasks_dir(base: Path | None = None) -> Path:
    return (base or config_dir()) / "tasks"


def load_task(task_id: str, base: Path | None = None) -> TaskSpec:
    return TaskSpec.model_validate(load_yaml(f"{task_id}.yaml", tasks_dir(base)))


def list_tasks(base: Path | None = None) -> list[str]:
    return sorted(p.stem for p in tasks_dir(base).glob("*.yaml"))

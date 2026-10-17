"""Image names and install or build recipes per executor and route.

Recipes are returned as lists of argument vectors so the CLI can print them (`--dry-run`) or run
them. Nothing here touches the network.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass, field
from pathlib import Path

from pah.runtimes.models import (
    AccelConfig,
    AccelSpec,
    Command,
    ExecutorRuntime,
    ImageRecipe,
    NativeRoute,
    Route,
    RuntimeProfile,
    RuntimeRegistry,
)


class RecipeError(ValueError):
    """The requested route or target does not exist for this executor."""


def kit_image_tag(reg: RuntimeRegistry, kit: str) -> str:
    return reg.kit_defaults.image_tag.format(kit=kit)


def native_image_ref(rt: ExecutorRuntime) -> str:
    """Docker reference of the stock image (pulled, built from upstream, or rendered here)."""
    native = _native(rt)
    if native.image is not None and native.image.pull:
        return native.image.pull
    if native.image is not None and native.image.tag:
        return native.image.tag
    return f"pah-{rt.id}:{native.version}"


def sif_name(rt: ExecutorRuntime, route: Route) -> str:
    if route is Route.NATIVE:
        return f"{rt.id}.sif"
    return f"{_accel(rt).kit}-kit.sif"


def _native(rt: ExecutorRuntime) -> NativeRoute:
    if rt.native is None:
        raise RecipeError(f"{rt.id}: no native route ({rt.native_note or 'kit image only'})")
    return rt.native


def _accel(rt: ExecutorRuntime) -> AccelSpec:
    if rt.accel is None:
        raise RecipeError(f"{rt.id}: no optimisation kit ({rt.accel_note or 'none published'})")
    return rt.accel


@dataclass
class Recipe:
    """Commands to run in order, plus files to write before running them."""

    commands: list[Command] = field(default_factory=list)
    files: dict[Path, str] = field(default_factory=dict)

    def render(self) -> str:
        lines = [f"# write {p} ({len(t.splitlines())} lines)" for p, t in self.files.items()]
        lines += [shlex.join(c) for c in self.commands]
        return "\n".join(lines)


# --------------------------------------------------------------------------- kits checkout


def fetch_kits(cfg: AccelConfig, reg: RuntimeRegistry, profile: RuntimeProfile) -> Recipe:
    """Sparse checkout of the kits repository at the pinned commit (shared core plus used kits)."""
    root = str(profile.path("kits_root"))
    kits = sorted({rt.accel.kit for rt in reg.executors if rt.accel is not None})
    return Recipe(
        commands=[
            ("git", "clone", "--filter=blob:none", "--no-checkout", cfg.repo, root),
            ("git", "-C", root, "sparse-checkout", "set", "--cone", "common", *kits),
            ("git", "-C", root, "checkout", "--detach", cfg.commit),
        ]
    )


# --------------------------------------------------------------------------- host installs


def install_native_host(
    reg: RuntimeRegistry, rt: ExecutorRuntime, profile: RuntimeProfile
) -> Recipe:
    """Install the stock tool into `<envs_root>/<id>` on a GPU host (no container)."""
    native = _native(rt)
    env_dir = profile.path("envs_root") / rt.id
    if native.kind == "pip":
        py = str(env_dir / "bin" / "python")
        return Recipe(
            commands=[
                ("uv", "venv", "--python", native.python or "3.11", str(env_dir)),
                ("uv", "pip", "install", "--python", py, *native.pip),
            ]
        )
    if native.kind == "binary":
        assert native.binary is not None
        target = env_dir / "bin" / native.binary.name
        cmds: list[Command] = [
            ("mkdir", "-p", str(target.parent)),
            ("curl", "-fL", "--retry", "3", "-o", str(target), native.binary.url),
        ]
        if native.binary.sha256:
            cmds.append(("sh", "-c", f"echo '{native.binary.sha256}  {target}' | sha256sum -c -"))
        cmds.append(("chmod", "+x", str(target)))
        return Recipe(commands=cmds)
    raise RecipeError(
        f"{rt.id}: the stock tool ships as an image; use "
        f"`pah runtimes build {rt.id} --route native --target docker|apptainer`"
    )


# --------------------------------------------------------------------------- images


def render_native_dockerfile(reg: RuntimeRegistry, rt: ExecutorRuntime) -> str:
    """Dockerfile for pip, binary and recipe routes."""
    base, steps = native_steps(reg, rt)
    body = [f"FROM {base}", "ENV DEBIAN_FRONTEND=noninteractive"]
    body += [f"RUN {s}" for s in steps]
    body.append('ENV PATH="/opt/executor/bin:${PATH}"')
    return "\n".join(body) + "\n"


def render_native_apptainer(reg: RuntimeRegistry, rt: ExecutorRuntime) -> str:
    """Apptainer definition with the same steps, buildable without Docker (`--fakeroot`)."""
    base, steps = native_steps(reg, rt)
    post = "\n".join(f"    {s}" for s in ["export DEBIAN_FRONTEND=noninteractive", *steps])
    return (
        f"Bootstrap: docker\nFrom: {base}\n\n%post\n{post}\n\n"
        '%environment\n    export PATH="/opt/executor/bin:$PATH"\n    export PYTHONNOUSERSITE=1\n'
    )


def native_steps(reg: RuntimeRegistry, rt: ExecutorRuntime) -> tuple[str, list[str]]:
    """Base image and shell steps for a rendered stock image."""
    native = _native(rt)
    base = reg.native_image.base
    apt = (
        "apt-get update && apt-get install -y --no-install-recommends curl ca-certificates git "
        "&& rm -rf /var/lib/apt/lists/*"
    )
    if native.kind == "pip":
        uv = (
            f"curl -fsSL {reg.native_image.uv_tarball} "
            "| tar -xz -C /usr/local/bin --strip-components=1"
        )
        pip = " ".join(shlex.quote(p) for p in native.pip)
        return base, [
            apt,
            uv,
            f"uv venv --python {native.python or '3.11'} /opt/executor",
            f"uv pip install --python /opt/executor/bin/python {pip}",
        ]
    if native.kind == "binary":
        assert native.binary is not None
        dst = f"/opt/executor/bin/{native.binary.name}"
        steps = [
            apt,
            "mkdir -p /opt/executor/bin",
            f"curl -fL --retry 3 -o {dst} {native.binary.url}",
        ]
        if native.binary.sha256:
            steps.append(f"echo '{native.binary.sha256}  {dst}' | sha256sum -c -")
        steps.append(f"chmod +x {dst}")
        return base, steps
    if native.image is not None and native.image.recipe is not None:
        recipe: ImageRecipe = native.image.recipe
        return recipe.base, list(recipe.steps)
    raise RecipeError(f"{rt.id}: stock image is pulled or built upstream; nothing to render")


def build_image(
    reg: RuntimeRegistry,
    rt: ExecutorRuntime,
    profile: RuntimeProfile,
    route: Route,
    target: str,
) -> Recipe:
    """Commands that produce the image a launcher runs (`target` is docker or apptainer)."""
    if target not in {"docker", "apptainer"}:
        raise RecipeError(f"unknown target {target!r}; expected docker or apptainer")
    images = profile.path("images_root")
    if route is not Route.NATIVE:
        return _build_kit(reg, rt, profile, target)
    native = _native(rt)
    ref = native_image_ref(rt)
    sif = str(images / sif_name(rt, Route.NATIVE))
    if native.image is not None and native.image.pull:
        if target == "docker":
            return Recipe(commands=[("docker", "pull", ref)])
        return Recipe(
            commands=[("mkdir", "-p", str(images)), ("apptainer", "build", sif, f"docker://{ref}")]
        )
    if native.image is not None and native.image.build is not None:
        b = native.image.build
        src = str(images / "src" / rt.id)
        cmds: list[Command] = [
            ("git", "clone", b.git, src),
            ("git", "-C", src, "checkout", "--detach", b.ref),
            ("docker", "build", "-f", f"{src}/{b.dockerfile}", "-t", ref, src),
        ]
        if target == "apptainer":
            cmds.append(("apptainer", "build", sif, f"docker-daemon://{ref}"))
        return Recipe(commands=cmds)
    ctx = images / "native" / rt.id
    if target == "docker":
        dockerfile = ctx / "Dockerfile"
        return Recipe(
            commands=[("docker", "build", "-t", ref, str(ctx))],
            files={dockerfile: render_native_dockerfile(reg, rt)},
        )
    definition = ctx / f"{rt.id}.def"
    return Recipe(
        commands=[("apptainer", "build", "--fakeroot", sif, str(definition))],
        files={definition: render_native_apptainer(reg, rt)},
    )


def _build_kit(
    reg: RuntimeRegistry, rt: ExecutorRuntime, profile: RuntimeProfile, target: str
) -> Recipe:
    kit = _accel(rt).kit
    kits = profile.path("kits_root")
    tag = kit_image_tag(reg, kit)
    dockerfile = kits / reg.kit_defaults.dockerfile.format(kit=kit)
    cmds: list[Command] = [("docker", "build", "-f", str(dockerfile), "-t", tag, str(kits))]
    if target == "apptainer":
        images = profile.path("images_root")
        definition = kits / reg.kit_defaults.apptainer_def.format(kit=kit)
        cmds += [
            ("mkdir", "-p", str(images)),
            ("apptainer", "build", str(images / sif_name(rt, Route.KIT)), str(definition)),
        ]
    return Recipe(commands=cmds)

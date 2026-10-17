"""Launchers turn an executor command into the process to start on this host.

host       run directly (a venv under envs_root, a binary on PATH, or inside the executor image)
docker     `docker run --gpus all` with bind mounts for inputs, outputs and weights
apptainer  `apptainer exec --nv --cleanenv` against a .sif under images_root (CSF3)
"""

from __future__ import annotations

import os
import shutil
import subprocess
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pah.runtimes.accel import Availability
from pah.runtimes.images import kit_image_tag, native_image_ref, sif_name
from pah.runtimes.models import Command, ExecutorRuntime, Route, RuntimeProfile, RuntimeRegistry


@dataclass(frozen=True)
class Invocation:
    argv: Command
    env: dict[str, str] = field(default_factory=dict)
    image: str | None = None


class Launcher(Protocol):
    name: str

    def kit_dir(self, kit: str) -> str: ...

    def kit_available(self, rt: ExecutorRuntime) -> Availability: ...

    def native_available(self, rt: ExecutorRuntime) -> Availability: ...

    def wrap(
        self,
        rt: ExecutorRuntime,
        route: Route,
        argv: Command,
        env: Mapping[str, str],
        binds: Iterable[Path],
    ) -> Invocation: ...


def _module_importable(python: str, module: str) -> bool:
    code = f"import importlib.util as u, sys; sys.exit(0 if u.find_spec({module!r}) else 1)"
    try:
        proc = subprocess.run([python, "-c", code], capture_output=True, timeout=60, check=False)
    except OSError:
        return False
    return proc.returncode == 0


class HostLauncher:
    """Runs commands on this host. A kit counts as available when its checkout exists and its
    package imports in the kit environment: `<envs_root>/<kit>-kit` (the kit's route-C venv)
    or, inside a kit image, the image's own python."""

    name = "host"

    def __init__(
        self,
        reg: RuntimeRegistry,
        profile: RuntimeProfile,
        which: Callable[[str], str | None] = shutil.which,
        importable: Callable[[str, str], bool] = _module_importable,
    ) -> None:
        self._reg = reg
        self._profile = profile
        self._which = which
        self._importable = importable

    def kit_dir(self, kit: str) -> str:
        return str(self._profile.path("kits_root") / kit)

    def _kit_bin(self, kit: str) -> Path:
        return self._profile.path("envs_root") / f"{kit}-kit" / "bin"

    def kit_available(self, rt: ExecutorRuntime) -> Availability:
        if rt.accel is None:
            return Availability(False, "no kit")
        kit = rt.accel.kit
        root = Path(self.kit_dir(kit))
        if not (root / "run.sh").is_file():
            return Availability(False, f"{root}/run.sh missing (pah runtimes kits fetch)")
        if self._profile.kit_probe == "checkout":
            return Availability(True, str(root / "run.sh"))
        packages = sorted(p.parent.name for p in root.glob("opt/*_opt/__init__.py"))
        if not packages:
            return Availability(False, f"no kit package under {root}/opt")
        local = self._kit_bin(kit) / "python"
        python = str(local) if local.exists() else (self._which("python3") or "python3")
        if self._importable(python, packages[0]):
            return Availability(True, f"{root} ({packages[0]} in {python})")
        return Availability(
            False,
            f"{packages[0]} not importable by {python}; install the kit stack ({root}/STOCK.md, "
            f"Stack) into {local.parent.parent} or use the docker or apptainer launcher",
        )

    def _env_bin(self, rt: ExecutorRuntime) -> Path:
        return self._profile.path("envs_root") / rt.id / "bin"

    def native_available(self, rt: ExecutorRuntime) -> Availability:
        if rt.native is None:
            return Availability(False, rt.native_note or "no native route")
        if rt.native.host_probe is not None:
            probe = Path(rt.native.host_probe)
            if probe.exists():
                return Availability(True, str(probe))
            return Availability(False, f"{probe} missing; this route runs inside its image")
        exe = rt.native.command[0]
        local = self._env_bin(rt) / exe
        if local.exists():
            return Availability(True, str(local))
        found = self._which(exe)
        if found:
            return Availability(True, found)
        return Availability(
            False, f"{exe} not in {local.parent} or on PATH (pah runtimes install {rt.id})"
        )

    def wrap(
        self,
        rt: ExecutorRuntime,
        route: Route,
        argv: Command,
        env: Mapping[str, str],
        binds: Iterable[Path],
    ) -> Invocation:
        extra = dict(env)
        if route is Route.NATIVE:
            bin_dir = self._env_bin(rt)
        else:
            assert rt.accel is not None
            bin_dir = self._kit_bin(rt.accel.kit)
        if bin_dir.is_dir():
            extra["PATH"] = f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}"
        return Invocation(argv=argv, env=extra)


def _docker_image_present(ref: str) -> bool:
    if shutil.which("docker") is None:
        return False
    proc = subprocess.run(
        ["docker", "image", "inspect", ref], capture_output=True, timeout=60, check=False
    )
    return proc.returncode == 0


class DockerLauncher:
    name = "docker"

    def __init__(
        self,
        reg: RuntimeRegistry,
        profile: RuntimeProfile,
        present: Callable[[str], bool] = _docker_image_present,
    ) -> None:
        self._reg = reg
        self._profile = profile
        self._present = present

    def kit_dir(self, kit: str) -> str:
        return self._reg.kit_defaults.dir_in_image.format(kit=kit)

    def image(self, rt: ExecutorRuntime, route: Route) -> str:
        if route is Route.NATIVE:
            return native_image_ref(rt)
        assert rt.accel is not None
        return kit_image_tag(self._reg, rt.accel.kit)

    def _available(self, rt: ExecutorRuntime, route: Route) -> Availability:
        ref = self.image(rt, route)
        if self._present(ref):
            return Availability(True, ref)
        return Availability(
            False, f"image {ref} not present (pah runtimes build {rt.id} --target docker)"
        )

    def kit_available(self, rt: ExecutorRuntime) -> Availability:
        return Availability(False, "no kit") if rt.accel is None else self._available(rt, Route.KIT)

    def native_available(self, rt: ExecutorRuntime) -> Availability:
        if rt.native is None:
            return Availability(False, rt.native_note or "no native route")
        return self._available(rt, Route.NATIVE)

    def wrap(
        self,
        rt: ExecutorRuntime,
        route: Route,
        argv: Command,
        env: Mapping[str, str],
        binds: Iterable[Path],
    ) -> Invocation:
        image = self.image(rt, route)
        cmd: list[str] = ["docker", "run", "--rm", "--ipc=host"]
        if rt.gpu:
            cmd += ["--gpus", "all"]
        for b in sorted({str(p) for p in binds}):
            cmd += ["-v", f"{b}:{b}"]
        for k, v in sorted(env.items()):
            cmd += ["-e", f"{k}={v}"]
        workdir = (
            rt.native.image.workdir
            if route is Route.NATIVE and rt.native and rt.native.image
            else None
        )
        if workdir:
            cmd += ["-w", workdir]
        return Invocation(argv=(*cmd, image, *argv), image=image)


class ApptainerLauncher:
    name = "apptainer"

    def __init__(self, reg: RuntimeRegistry, profile: RuntimeProfile) -> None:
        self._reg = reg
        self._profile = profile

    def kit_dir(self, kit: str) -> str:
        return self._reg.kit_defaults.dir_in_image.format(kit=kit)

    def sif(self, rt: ExecutorRuntime, route: Route) -> Path:
        return self._profile.path("images_root") / sif_name(rt, route)

    def _available(self, rt: ExecutorRuntime, route: Route) -> Availability:
        sif = self.sif(rt, route)
        if sif.is_file():
            return Availability(True, str(sif))
        return Availability(False, f"{sif} missing (pah runtimes build {rt.id} --target apptainer)")

    def kit_available(self, rt: ExecutorRuntime) -> Availability:
        return Availability(False, "no kit") if rt.accel is None else self._available(rt, Route.KIT)

    def native_available(self, rt: ExecutorRuntime) -> Availability:
        if rt.native is None:
            return Availability(False, rt.native_note or "no native route")
        return self._available(rt, Route.NATIVE)

    def wrap(
        self,
        rt: ExecutorRuntime,
        route: Route,
        argv: Command,
        env: Mapping[str, str],
        binds: Iterable[Path],
    ) -> Invocation:
        sif = str(self.sif(rt, route))
        cmd: list[str] = ["apptainer", "exec", "--cleanenv"]
        if rt.gpu:
            cmd.append("--nv")
        bound = sorted({str(p) for p in binds})
        if bound:
            cmd += ["--bind", ",".join(bound)]
        for k, v in sorted(env.items()):
            cmd += ["--env", f"{k}={v}"]
        workdir = (
            rt.native.image.workdir
            if route is Route.NATIVE and rt.native and rt.native.image
            else None
        )
        if workdir:
            cmd += ["--pwd", workdir]
        return Invocation(argv=(*cmd, sif, *argv), image=sif)


LAUNCHERS: dict[str, Callable[[RuntimeRegistry, RuntimeProfile], Launcher]] = {
    "host": HostLauncher,
    "docker": DockerLauncher,
    "apptainer": ApptainerLauncher,
}


def make_launcher(name: str, reg: RuntimeRegistry, profile: RuntimeProfile) -> Launcher:
    try:
        return LAUNCHERS[name](reg, profile)
    except KeyError as exc:
        raise ValueError(f"unknown launcher {name!r}; expected one of {sorted(LAUNCHERS)}") from exc

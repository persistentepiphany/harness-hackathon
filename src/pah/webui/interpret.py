"""Rule-based request interpreter. No language model is called.

A deterministic port of `interpretRun(text)` in `web/design/prototype/data/runs.js`: the same
regular expressions, applied in the same order, return the same settings and the same
`{field, value, because}` steps. Entities come from `configs/catalog.yaml`, tool ids are the
executor ids of `configs/executors.yaml`, and each task's claim is read from its specification.

Differences from the prototype:
- Only Quick setup tasks (`quickSetup: true` in configs/catalog.yaml) are picked. A request that
  matches a task offered only in manual setup gets a `warning` step and falls through to the next
  rule; interaction words map to the complex-structure task, ranking words to series ranking.
- "decoy partners" is not a screening library; "protein-protein dock" (without "-ing") is
  protein-protein docking.
- Every task that takes a partner gets one (the prototype set it for interaction discovery only).
- A tool the user names is kept. When its configs/models.yaml endpoints lack the task endpoint,
  or a required input is missing (a series of one ligand), the result lists the problem in
  `warnings` and in a `warning` step. Defaults always have the endpoint.
Data and explanation differences:
- Tool ids are executor ids (`af3` becomes `alphafold3`, `haddock` becomes `haddock3`), and any
  executor in the register is recognised by id or name, not only the prototype's ten.
- The `reference` step says "PDB entry named in the request" only when the value is that entry;
  the prototype said so whenever any PDB-like token appeared.
- Catalog values that the prototype mocked are replaced by public values (for example ABL1's
  reference is 2HYY, human Abl with imatinib, where the prototype used mouse Abl 1IEP).
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from typing import Any

from pah.webui.catalog import Catalog, Executor, load_catalog, load_executors

_A = re.ASCII  # JavaScript \b, \d and \w are ASCII-only without the u flag

_TASK_RULES: tuple[tuple[str, re.Pattern[str], re.Pattern[str] | None], ...] = (
    ("virtual_screening", re.compile(r"screen|library|enrich|decoys?(?! partner)", _A), None),
    ("redocking", re.compile(r"redock", _A), None),
    ("blind_docking", re.compile(r"blind", _A), None),
    ("variant_effect", re.compile(r"variant|mutant|mutation|resistan", _A), None),
    ("design_validation", re.compile(r"design(ed)?\b|binder design|self-consisten", _A), None),
    (
        "monomer",
        re.compile(r"monomer|fold of|structure of\b", _A),
        re.compile(r"complex|partner|ligand|dock", _A),
    ),
    ("binding_site", re.compile(r"binding site|where does|which pocket|site identif", _A), None),
    ("affinity_ranking", re.compile(r"affinit", _A), re.compile(r"dock|vina|gnina|score", _A)),
    ("series_scoring", re.compile(r"rank|series|analog|congeneric|sar\b|affinit", _A), None),
    ("protein_protein_docking", re.compile(r"pydock|haddock|protein.protein dock", _A), None),
    (
        "known_complex",
        re.compile(r"known complex|complex structure|assembl|stoichiometr", _A),
        None,
    ),
    (
        "interaction_discovery",
        re.compile(r"interact|partner|bind(s|ing)? to|complex with|discover", _A),
        re.compile(r"pocket|dock|pose|ligand", _A),
    ),
    (
        "known_complex",
        re.compile(r"interact|partner|bind(s|ing)? to|complex with|complex of", _A),
        re.compile(r"pocket|dock|pose|ligand", _A),
    ),
    (
        "pose_known_pocket",
        re.compile(r"dock", _A),
        re.compile(r"boltz|protenix|alphafold|chai|co-?fold", _A),
    ),
)
_DEFAULT_TASK = "ligand_pose"
_TASK_WORDS = re.compile(
    r"screen|redock|blind|variant|design|monomer|site|dock|pose|pocket|rank|series|analog|"
    r"congeneric|interact|partner|discover|assembl|bind\w*",
    _A,
)
_ACCESSION = re.compile(
    r"\b[OPQ][0-9][A-Z0-9]{3}[0-9]\b|\b[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]\b", _A
)
_SMILES_RUN = re.compile(r"[A-Za-z0-9@+\-\[\]()\\/%=#$.]{12,}", _A)
_SMILES_HINT = re.compile(r"[=#()\[\]]", _A)
_SEEDS = re.compile(r"(\d+)\s*seeds?", _A)
_PH = re.compile(r"ph\s*([\d.]+)", _A)
_PDB = re.compile(r"\b[1-9][A-Za-z0-9]{3}\b", _A)

ClaimFn = Callable[[str], str | None]
EndpointFn = Callable[[str], list[str]]
TaskEndpointFn = Callable[[str], str | None]


def _model_endpoints(executor: str) -> list[str]:
    from pah.webui.adapter import model_endpoints

    return model_endpoints(executor)


def _task_endpoint(pah_task: str) -> str | None:
    from pah.webui.adapter import task_endpoint

    return task_endpoint(pah_task)


def _spec_claim(pah_task: str) -> str | None:
    from pah.core.task import load_task

    try:
        return load_task(pah_task).claim
    except (OSError, ValueError):
        return None


def _js_number(text: str) -> float | int | None:
    """`+text` in JavaScript for a string of digits and dots; NaN becomes None (JSON null)."""
    try:
        value = float(text)
    except ValueError:
        return None
    if math.isnan(value):
        return None
    return int(value) if value.is_integer() else value


def _tool_matchers(catalog: Catalog, executors: tuple[Executor, ...]) -> list[tuple[str, str, str]]:
    """(id, lower-case name, output id) in catalog order, then the other register executors."""
    out = [(t.id, t.name.lower(), t.executor or t.id) for t in catalog.tools]
    covered = {t.executor for t in catalog.tools if t.executor}
    out += [(e.id, e.name.lower(), e.id) for e in executors if e.id not in covered]
    return out


def _unique(items: list[str]) -> list[str]:
    seen: list[str] = []
    for i in items:
        if i not in seen:
            seen.append(i)
    return seen


def interpret_request(
    text: str,
    catalog: Catalog | None = None,
    executors: tuple[Executor, ...] | None = None,
    claim_for: ClaimFn = _spec_claim,
    endpoints_of: EndpointFn = _model_endpoints,
    endpoint_for: TaskEndpointFn = _task_endpoint,
) -> dict[str, Any]:
    """Settings and the reasons for each decision, in the shape `interpretRun` returns, plus
    `warnings` (problems with the request, kept as written)."""
    cat = catalog or load_catalog()
    register = executors if executors is not None else load_executors()
    t = text.lower()
    steps: list[dict[str, Any]] = []
    warnings: list[str] = []
    offered = {x.id for x in cat.tasks if x.quick_setup} or {x.id for x in cat.tasks}

    task = _DEFAULT_TASK
    for task_id, pattern, unless in _TASK_RULES:
        if pattern.search(t) and not (unless and unless.search(t)):
            if task_id not in offered:
                skipped = cat.task(task_id)
                name = skipped.name.lower() if skipped else task_id
                if not any(task_id in w for w in warnings):
                    warnings.append(
                        f"request matches {name} ({task_id}), which Quick setup does not "
                        "offer; use manual setup for it"
                    )
                continue
            task = task_id
            break
    words = _unique(_TASK_WORDS.findall(t)[:3])
    steps.append(
        {
            "field": "task",
            "value": task,
            "because": f"matched “{'”, “'.join(words)}”" if words else "default for a ligand input",
        }
    )

    task_def = cat.task(task)
    named = _unique(
        [out for tid, name, out in _tool_matchers(cat, register) if name in t or tid in t]
    )
    defaults = [
        (entry.executor or entry.id) if (entry := cat.tool(x)) else x
        for x in (task_def.default_tools if task_def else ())
    ]
    tools = named or _unique(defaults)
    task_name = task_def.name.lower() if task_def else task
    families = {e.family for e in register if e.id in tools}
    pair = "cross-family pair" if len(families) > 1 else "default tools"
    steps.append(
        {
            "field": "tools",
            "value": tools,
            "because": "named in the request" if named else f"task default: {pair} for {task_name}",
        }
    )
    endpoint = endpoint_for(task_def.pah) if task_def else None
    executor_ids = {e.id for e in register}
    for tool in tools:
        if endpoint is None or tool not in executor_ids:
            continue
        if endpoint not in endpoints_of(tool):
            warnings.append(
                f"{tool} does not produce {endpoint}, the endpoint {task_name} needs "
                "(configs/models.yaml); kept as named, layer 3 l3.metric.endpoint will stop it"
            )

    prots = [p for p in cat.proteins if any(n in t for n in p.names)]
    acc = _ACCESSION.search(text)
    if prots:
        target, because = prots[0].accession, f"“{prots[0].label}” → UniProt {prots[0].accession}"
    elif acc:
        target, because = acc.group(0), "accession given explicitly"
    else:
        target, because = cat.defaults.target, "no target recognised; example target used"
    steps.append({"field": "target", "value": target, "because": because})

    partner = ""
    takes = set(task_def.inputs) if task_def else set()
    if "partner" in takes or task == "interaction_discovery":
        if len(prots) > 1:
            partner = prots[1].accession
            because = f"“{prots[1].label}” → UniProt {partner}"
        else:
            partner, because = cat.defaults.partner, "no partner recognised; example partner used"
        steps.append({"field": "partner", "value": partner, "because": because})

    lig = next((x for x in cat.ligands if any(n in t for n in x.names)), None)
    smiles = next((s for s in _SMILES_RUN.findall(text) if _SMILES_HINT.search(s)), None)
    ligand = ""
    if "series" in takes:
        warnings.append(
            f"{task_name} ranks a ligand series; the run settings carry one ligand, so the "
            "ranking checks have one member until a series is supplied"
        )
    if takes and not ({"ligand", "series"} & takes):
        pass
    elif task != "interaction_discovery":
        if lig is not None:
            ligand, because = lig.smiles, f"“{lig.names[0]}” → CCD {lig.ccd}, PubChem {lig.cid}"
        elif smiles:
            ligand = smiles
            because = "SMILES given explicitly, identity will be checked by InChIKey"
        else:
            example = cat.ligand_by_name(cat.defaults.ligand) or cat.ligands[0]
            ligand, because = example.smiles, "no ligand recognised; example ligand used"
        steps.append({"field": "ligand", "value": ligand, "because": because})

    seed_match = _SEEDS.search(t)
    seeds = min(20, max(1, int(seed_match.group(1)))) if seed_match else 5
    steps.append(
        {
            "field": "seeds",
            "value": seeds,
            "because": "stated in the request"
            if seed_match
            else "task default (five independent seeds, counted separately from diffusion samples)",
        }
    )
    ph_match = _PH.search(t)
    ph = _js_number(ph_match.group(1)) if ph_match else 7.4
    steps.append(
        {
            "field": "ph",
            "value": ph,
            "because": "stated in the request"
            if ph_match
            else "physiological default; protonation enumerated at this pH",
        }
    )

    pdb_match = _PDB.search(text)
    named_pdb = pdb_match.group(0).upper() if pdb_match else None
    reference = (prots[0].pdb if prots else None) or named_pdb or cat.defaults.reference
    steps.append(
        {
            "field": "reference",
            "value": reference,
            "because": "PDB entry named in the request"
            if named_pdb and reference == named_pdb
            else "holo entry for the target from RCSB, used for redocking control",
        }
    )

    claim = claim_for(task_def.pah) if task_def else None
    steps.append(
        {
            "field": "claim",
            "value": claim,
            "because": "the only claim this task is permitted to support"
            if claim
            else f"no task specification found for {task}",
        }
    )
    steps += [{"field": "warning", "value": w, "because": w} for w in warnings]
    return {
        "warnings": warnings,
        "task": task,
        "tools": tools,
        "target": target,
        "partner": partner,
        "ligand": ligand,
        "seeds": seeds,
        "ph": ph,
        "reference": reference,
        "claim": claim,
        "steps": steps,
    }

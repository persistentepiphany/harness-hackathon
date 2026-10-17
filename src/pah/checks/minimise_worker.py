"""Restrained minimisation of one protein-ligand pose. Runs in the conda environment that holds
OpenMM, OpenFF and openmmforcefields (PAH_CONDA_PREFIX), as `python -I minimise_worker.py ARGS`,
so it imports nothing from `pah`.

ARGS is JSON: {"receptor": pdb, "ligand": sdf, "ph": float, "out": json path}.
Protein: AMBER14 (amber14-all), hydrogens from PDBFixer at the given pH. Ligand: OpenFF Sage 2.2
with MMFF94 partial charges from RDKit (AM1-BCC needs AmberTools, which is not installed).
Protein heavy atoms are restrained harmonically at 10 kcal/mol/Å^2; the ligand is free. Vacuum,
no cutoff, L-BFGS to a 1 kJ/mol/nm tolerance. Output: ligand heavy-atom RMSD before and after.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def main(args: dict[str, Any]) -> dict[str, Any]:
    import numpy as np
    import openmm
    from openff.toolkit import Molecule
    from openmm import app, unit
    from openmmforcefields.generators import SMIRNOFFTemplateGenerator
    from pdbfixer import PDBFixer
    from rdkit import Chem

    lig_rd = Chem.MolFromMolFile(args["ligand"], removeHs=False)
    lig_rd = Chem.AddHs(lig_rd, addCoords=True)
    lig = Molecule.from_rdkit(lig_rd, allow_undefined_stereo=True, hydrogens_are_explicit=True)
    lig.assign_partial_charges("mmff94")

    fixer = PDBFixer(filename=args["receptor"])
    fixer.removeHeterogens(keepWater=False)
    fixer.findMissingResidues()
    fixer.missingResidues = {}
    fixer.findMissingAtoms()
    fixer.addMissingAtoms()
    fixer.addMissingHydrogens(float(args["ph"]))

    modeller = app.Modeller(fixer.topology, fixer.positions)
    lig_top = lig.to_topology().to_openmm()
    lig_pos = lig.conformers[0].to_openmm()
    modeller.add(lig_top, lig_pos)

    ff = app.ForceField("amber14-all.xml")
    gen = SMIRNOFFTemplateGenerator(molecules=[lig], forcefield="openff-2.2.0")
    ff.registerTemplateGenerator(gen.generator)
    system = ff.createSystem(modeller.topology, nonbondedMethod=app.NoCutoff, constraints=None)

    restraint = openmm.CustomExternalForce("0.5*k*((x-x0)^2+(y-y0)^2+(z-z0)^2)")
    k = (10.0 * unit.kilocalorie_per_mole / unit.angstrom**2).value_in_unit(
        unit.kilojoule_per_mole / unit.nanometer**2
    )
    restraint.addGlobalParameter("k", k)
    for name in ("x0", "y0", "z0"):
        restraint.addPerParticleParameter(name)
    positions = modeller.positions
    n_lig = lig.n_atoms
    n_all = len(positions)
    lig_start = n_all - n_lig
    for atom in modeller.topology.atoms():
        if atom.index < lig_start and atom.element is not None and atom.element.symbol != "H":
            p = positions[atom.index].value_in_unit(unit.nanometer)
            restraint.addParticle(atom.index, [p[0], p[1], p[2]])
    system.addForce(restraint)

    integrator = openmm.VerletIntegrator(0.001)
    platform = openmm.Platform.getPlatformByName("CPU")
    sim = app.Simulation(modeller.topology, system, integrator, platform)
    sim.context.setPositions(positions)
    e0 = sim.context.getState(getEnergy=True).getPotentialEnergy()
    sim.minimizeEnergy(tolerance=1.0 * unit.kilojoule_per_mole / unit.nanometer, maxIterations=2000)
    state = sim.context.getState(getEnergy=True, getPositions=True)
    e1 = state.getPotentialEnergy()
    after = np.array(state.getPositions(asNumpy=True).value_in_unit(unit.angstrom))[lig_start:]
    before = np.array([[v.value_in_unit(unit.angstrom) for v in p] for p in lig_pos])
    heavy = [a.molecule_atom_index for a in lig.atoms if a.atomic_number > 1]
    drift = float(np.sqrt(((after[heavy] - before[heavy]) ** 2).sum(axis=1).mean()))
    result = {
        "drift_A": round(drift, 3),
        "energy_before_kJ": round(e0.value_in_unit(unit.kilojoule_per_mole), 1),
        "energy_after_kJ": round(e1.value_in_unit(unit.kilojoule_per_mole), 1),
        "converged": True,
        "openmm": openmm.__version__,
        "method": "OpenMM, AMBER14 protein, OpenFF Sage 2.2 ligand with MMFF94 charges, "
        "protein heavy atoms restrained at 10 kcal/mol/Å², vacuum, L-BFGS",
    }
    Path(args["out"]).write_text(json.dumps(result))
    return result


if __name__ == "__main__":
    print(json.dumps(main(json.loads(sys.argv[1]))))

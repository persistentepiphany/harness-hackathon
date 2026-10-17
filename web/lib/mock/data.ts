// TypeScript port of web/design/prototype/data/runs.js (mock data, interpreter, entity lookups).
// The logic is kept identical to the prototype. Additions, all marked "addition":
// - TOOLS carry `outputs` and `dockingParams` (keys from docs/EXECUTORS.md "Parsed fields"),
// - stats.metrics / stats.ensemble / docking reference those keys (toolId, key, values, params),
// - layers carry `status` and `counts`, the record carries `source: 'mock'`.
// Mock mode only: none of these values come from a computation.

import type {
  AgreementRow,
  CatalogLigand,
  CatalogProtein,
  DockingCard,
  EnsembleEntry,
  EntityGroup,
  ExecutionLine,
  InteractionRow,
  PerturbationRow,
  PhysicsRow,
  PoseBustersTest,
  RecordLayer,
  RecordSource,
  RecordTool,
  Result,
  RunSettings,
  SeedStat,
  Step,
  Task,
  Tool,
  ToolOutput,
  UiCheck,
  UiMetric,
  UiRunRecord,
  UiStats,
  Verdict,
} from '../types';

// ---------------------------------------------------------------- tool register (mock)

const confidence = (key: string, label: string, scope: ToolOutput['scope'] = 'global'): ToolOutput => ({
  key,
  label,
  kind: 'confidence',
  scope,
  range: [0, 1],
  higherIsBetter: true,
});

export const TOOLS: Tool[] = [
  {
    id: 'boltz2', name: 'Boltz-2', family: 'co-folding', role: 'Executor and affinity', version: '2.1.1', available: true,
    licence: 'MIT', repo: 'https://github.com/jwohlwend/boltz',
    outputs: [
      confidence('confidence_score', 'Confidence'),
      confidence('ptm', 'pTM'),
      { key: 'iptm', label: 'ipTM', kind: 'interface', scope: 'interface', range: [0, 1], higherIsBetter: true },
      { key: 'ligand_iptm', label: 'Ligand ipTM', kind: 'interface', scope: 'ligand', range: [0, 1], higherIsBetter: true },
      { key: 'complex_plddt', label: 'Complex pLDDT', kind: 'plddt', scope: 'global', range: [0, 1], higherIsBetter: true },
      { key: 'complex_iplddt', label: 'Interface pLDDT', kind: 'plddt', scope: 'interface', range: [0, 1], higherIsBetter: true },
      { key: 'complex_pde', label: 'Complex PDE', unit: 'Å', kind: 'pae', scope: 'global', higherIsBetter: false },
      { key: 'complex_ipde', label: 'Interface PDE', unit: 'Å', kind: 'pae', scope: 'interface', higherIsBetter: false },
      { key: 'affinity_pred_value', label: 'Affinity', unit: 'log10 µM', kind: 'affinity', scope: 'ligand', higherIsBetter: false, rankingOnly: true, note: 'log10(IC50 µM); lower is stronger' },
      { key: 'affinity_probability_binary', label: 'Binder probability', kind: 'affinity', scope: 'ligand', range: [0, 1], higherIsBetter: true, rankingOnly: true },
    ],
  },
  {
    id: 'protenix', name: 'Protenix', family: 'co-folding', role: 'Executor', version: '0.5.0', available: true,
    licence: 'Apache-2.0', repo: 'https://github.com/bytedance/Protenix',
    outputs: [
      { key: 'plddt', label: 'pLDDT', kind: 'plddt', scope: 'global', range: [0, 100], higherIsBetter: true },
      confidence('ptm', 'pTM'),
      { key: 'iptm', label: 'ipTM', kind: 'interface', scope: 'interface', range: [0, 1], higherIsBetter: true },
      { key: 'gpde', label: 'Global PDE', unit: 'Å', kind: 'pae', scope: 'global', higherIsBetter: false },
      { key: 'ranking_score', label: 'Ranking score', kind: 'score', scope: 'global', higherIsBetter: true, note: '0.8·ipTM + 0.2·pTM + 0.5·disorder − 100·has_clash' },
      { key: 'has_clash', label: 'Clash flag', kind: 'other', scope: 'global', higherIsBetter: false },
    ],
  },
  {
    id: 'af3', name: 'AlphaFold3', family: 'co-folding', role: 'Executor', version: '3.0.1', available: false, note: 'weights by request',
    repo: 'https://github.com/google-deepmind/alphafold3',
    outputs: [
      confidence('ptm', 'pTM'),
      { key: 'iptm', label: 'ipTM', kind: 'interface', scope: 'interface', range: [0, 1], higherIsBetter: true },
      { key: 'ranking_score', label: 'Ranking score', kind: 'score', scope: 'global', higherIsBetter: true },
      { key: 'fraction_disordered', label: 'Fraction disordered', kind: 'other', scope: 'global', range: [0, 1], higherIsBetter: false },
      { key: 'has_clash', label: 'Clash flag', kind: 'other', scope: 'global', higherIsBetter: false },
    ],
  },
  {
    id: 'chai1', name: 'Chai-1', family: 'co-folding', role: 'Executor', version: '0.6.1', available: true,
    repo: 'https://github.com/chaidiscovery/chai-lab',
    outputs: [
      { key: 'aggregate_score', label: 'Aggregate score', kind: 'score', scope: 'global', higherIsBetter: true, note: '0.2·pTM + 0.8·ipTM − 100·clashes' },
      confidence('ptm', 'pTM'),
      { key: 'iptm', label: 'ipTM', kind: 'interface', scope: 'interface', range: [0, 1], higherIsBetter: true },
      { key: 'has_inter_chain_clashes', label: 'Inter-chain clashes', kind: 'other', scope: 'interface', higherIsBetter: false },
    ],
  },
  {
    id: 'afdb', name: 'AlphaFold DB', family: 'co-folding', role: 'Lookup, monomers', version: 'v4', available: true,
    outputs: [{ key: 'plddt', label: 'pLDDT', kind: 'plddt', scope: 'global', range: [0, 100], higherIsBetter: true }],
  },
  {
    id: 'gnina', name: 'Gnina', family: 'docking', role: 'Executor, CNN rescoring', version: '1.3', available: true,
    licence: 'GPL-2.0 / Apache-2.0', repo: 'https://github.com/gnina/gnina',
    outputs: [
      { key: 'CNNscore', label: 'CNN pose score', kind: 'score', scope: 'pose', range: [0, 1], higherIsBetter: true },
      { key: 'minimizedRMSD', label: 'Minimised RMSD', unit: 'Å', kind: 'rmsd', scope: 'pose', higherIsBetter: false },
      { key: 'CNNaffinity', label: 'CNN affinity', unit: 'pK', kind: 'affinity', scope: 'pose', higherIsBetter: true, rankingOnly: true },
      { key: 'minimizedAffinity', label: 'Vina score', unit: 'kcal/mol', kind: 'affinity', scope: 'pose', higherIsBetter: false, rankingOnly: true },
    ],
    dockingParams: [
      { key: 'autobox_add', label: 'Autobox margin', unit: 'Å', default: '4' },
      { key: 'exhaustiveness', label: 'Exhaustiveness', default: '8' },
      { key: 'num_modes', label: 'Poses per seed', default: '9' },
      { key: 'cnn_scoring', label: 'CNN scoring', default: 'rescore' },
    ],
  },
  {
    id: 'vina', name: 'AutoDock Vina', family: 'docking', role: 'Executor', version: '1.2.5', available: true,
    licence: 'Apache-2.0', repo: 'https://github.com/ccsb-scripps/AutoDock-Vina',
    outputs: [
      { key: 'vina_score', label: 'Vina score', unit: 'kcal/mol', kind: 'affinity', scope: 'pose', higherIsBetter: false, rankingOnly: true },
      { key: 'rmsd_lb', label: 'RMSD l.b. to best mode', unit: 'Å', kind: 'rmsd', scope: 'pose', higherIsBetter: false },
      { key: 'rmsd_ub', label: 'RMSD u.b. to best mode', unit: 'Å', kind: 'rmsd', scope: 'pose', higherIsBetter: false },
    ],
    dockingParams: [
      { key: 'size', label: 'Box', unit: 'Å' },
      { key: 'exhaustiveness', label: 'Exhaustiveness', default: '8' },
      { key: 'num_modes', label: 'Poses per seed', default: '9' },
      { key: 'energy_range', label: 'Energy range', unit: 'kcal/mol', default: '3.0' },
    ],
  },
  {
    id: 'diffdock', name: 'DiffDock-L', family: 'docking', role: 'Learned docking', version: '1.1', available: true,
    repo: 'https://github.com/gcorso/DiffDock',
    outputs: [
      { key: 'confidence', label: 'Confidence', kind: 'confidence', scope: 'pose', higherIsBetter: true, note: 'raw confidence-model output, can be negative' },
      { key: 'rank', label: 'Rank', kind: 'other', scope: 'pose', higherIsBetter: false },
    ],
    dockingParams: [
      { key: 'samples_per_complex', label: 'Samples per complex', default: '10' },
      { key: 'inference_steps', label: 'Inference steps', default: '20' },
    ],
  },
  {
    id: 'pydock', name: 'pyDock', family: 'docking', role: 'Protein–protein docking', version: '3.0', available: false, note: 'academic licence',
    outputs: [],
  },
  {
    id: 'haddock', name: 'HADDOCK', family: 'docking', role: 'Protein–protein docking', version: '2.5', available: false, note: 'academic licence',
    repo: 'https://github.com/haddocking/haddock3',
    outputs: [
      { key: 'score', label: 'HADDOCK score', kind: 'score', scope: 'pose', higherIsBetter: false, rankingOnly: true },
      { key: 'dockq', label: 'DockQ', kind: 'interface', scope: 'interface', range: [0, 1], higherIsBetter: true },
      { key: 'irmsd', label: 'Interface RMSD', unit: 'Å', kind: 'rmsd', scope: 'interface', higherIsBetter: false },
      { key: 'fnat', label: 'Fnat', kind: 'interface', scope: 'interface', range: [0, 1], higherIsBetter: true },
    ],
  },
];

export const TASKS: Task[] = [
  // Co-folding task classes
  { id: 'monomer', group: 'co-folding', kind: 'monomer', name: 'Monomer structure', long: 'Monomer structure', defaultTools: ['boltz2', 'afdb'], claim: 'Fold of confident regions', controls: [], inputs: ['target', 'seeds'] },
  { id: 'known_complex', group: 'co-folding', kind: 'complex', name: 'Known complex', long: 'Known complex assembly', defaultTools: ['boltz2', 'protenix'], claim: 'Interface geometry, scoped by exposure', controls: ['Exposure report'], inputs: ['target', 'partner', 'reference', 'seeds'] },
  { id: 'interaction_discovery', group: 'co-folding', kind: 'complex', name: 'Interaction discovery', long: 'Interaction discovery', defaultTools: ['boltz2', 'protenix'], claim: 'Plausible relative to controls, never that the proteins bind', controls: ['Decoy partners', 'Sticky control', 'Known positive'], inputs: ['target', 'partner', 'reference', 'seeds'] },
  { id: 'ligand_pose', group: 'co-folding', kind: 'ligand', name: 'Ligand pose', long: 'Ligand pose in a known pocket', defaultTools: ['boltz2', 'gnina'], claim: 'Pose within stated uncertainty', controls: ['Redocking of a known ligand'], inputs: ['target', 'ligand', 'reference', 'ph', 'seeds'] },
  { id: 'binding_site', group: 'co-folding', kind: 'ligand', name: 'Binding site', long: 'Binding site identification', defaultTools: ['boltz2', 'protenix'], claim: 'Candidate sites ranked', controls: ['Known sites from PDBe-KB'], inputs: ['target', 'ligand', 'seeds'] },
  { id: 'affinity_ranking', group: 'co-folding', kind: 'ligand', name: 'Affinity ranking', long: 'Affinity ranking within a congeneric series', defaultTools: ['boltz2', 'gnina'], claim: 'Relative order within a congeneric series, never absolute affinity', controls: ['Known actives and inactives from ChEMBL', 'Target-specific recalibration'], inputs: ['target', 'series', 'reference', 'ph', 'seeds'] },
  { id: 'variant_effect', group: 'co-folding', kind: 'ligand', name: 'Variant effect', long: 'Variant effect', defaultTools: ['boltz2', 'chai1'], claim: 'Change detected, or not distinguishable from model noise', controls: ['Wild type against itself across seeds'], inputs: ['target', 'ligand', 'reference', 'seeds'] },
  { id: 'design_validation', group: 'co-folding', kind: 'complex', name: 'Design validation', long: 'Design validation', defaultTools: ['boltz2', 'protenix'], claim: 'Design is self-consistent, not that it binds', controls: ['Scrambled or non-cognate designs'], inputs: ['target', 'partner', 'seeds'] },
  // Docking task classes
  { id: 'redocking', group: 'docking', kind: 'ligand', name: 'Redocking', long: 'Redocking of the crystal ligand', defaultTools: ['vina', 'gnina'], claim: 'The protocol reproduces known poses on this receptor', controls: ['It is itself the control'], inputs: ['target', 'ligand', 'reference', 'ph', 'seeds'] },
  { id: 'pose_known_pocket', group: 'docking', kind: 'ligand', name: 'Docked pose', long: 'Pose prediction in a known pocket', defaultTools: ['gnina', 'diffdock'], claim: 'Pose within stated uncertainty', controls: ['Redocking on the same receptor'], inputs: ['target', 'ligand', 'reference', 'ph', 'seeds'] },
  { id: 'blind_docking', group: 'docking', kind: 'ligand', name: 'Blind docking', long: 'Blind docking', defaultTools: ['diffdock', 'gnina'], claim: 'Candidate sites, low confidence', controls: ['Known site where one exists'], inputs: ['target', 'ligand', 'seeds'] },
  { id: 'virtual_screening', group: 'docking', kind: 'ligand', name: 'Virtual screening', long: 'Virtual screening', defaultTools: ['vina', 'gnina'], claim: 'Enrichment over decoys, not individual affinities', controls: ['Property-matched decoys or confirmed inactives'], inputs: ['target', 'series', 'reference', 'ph', 'seeds'] },
  { id: 'series_scoring', group: 'docking', kind: 'ligand', name: 'Series scoring', long: 'Series scoring', defaultTools: ['gnina', 'vina'], claim: 'Weak ranking, explicitly flagged', controls: ['Known actives from ChEMBL'], inputs: ['target', 'series', 'reference', 'ph', 'seeds'] },
  { id: 'protein_protein_docking', group: 'docking', kind: 'complex', name: 'Protein–protein docking', long: 'Protein–protein docking', defaultTools: ['pydock', 'haddock'], claim: 'Candidate arrangements', controls: ['Non-cognate partner'], inputs: ['target', 'partner', 'reference', 'seeds'] },
];

export interface MockLayerDef {
  i: number;
  key: string;
  name: string;
  question: string;
  budget: string;
  ms: number;
}

export const LAYERS: MockLayerDef[] = [
  { i: 0, key: 'provenance', name: 'Provenance', question: 'Where did every input come from?', budget: '2–5 s', ms: 2600 },
  { i: 1, key: 'integrity', name: 'Input integrity', question: 'Did the run receive exactly what was declared?', budget: '2–3 s', ms: 1800 },
  { i: 2, key: 'adequacy', name: 'Input adequacy', question: 'Does the input carry enough information?', budget: '8–12 s', ms: 4200 },
  { i: 3, key: 'applicability', name: 'Applicability', question: 'Is the tool inside its validated regime?', budget: '2–3 s', ms: 1800 },
  { i: 4, key: 'validity', name: 'Output validity', question: 'Is the result physically and chemically sensible?', budget: '10–25 s', ms: 5600 },
  { i: 5, key: 'support', name: 'Output support', question: 'Is a valid result corroborated?', budget: '3–5 s', ms: 2400 },
];

// ---- Known entities the mocked interpreter can resolve. ----
const ENTITIES: { proteins: CatalogProtein[]; ligands: CatalogLigand[] } = {
  proteins: [
    { names: ['abl1', 'abl', 'bcr-abl', 'p00519'], accession: 'P00519', entry: 'ABL1_HUMAN', label: 'ABL1 kinase', organism: 'Homo sapiens', length: 1130, pdb: '1IEP', resolution: '2.10 Å', holo: 14, afPlddt: 88, sites: 3, domains: 'SH3 · SH2 · Protein kinase', disorder: '12% (N-terminal cap, C-terminal tail)', cofactors: 'Mg²⁺ · ATP site' },
    { names: ['mac1', 'nsp3', 'macrodomain', 'p0dtd1'], accession: 'P0DTD1', entry: 'R1AB_SARS2', label: 'SARS-CoV-2 Mac1', organism: 'SARS-CoV-2', length: 7096, pdb: '7KQO', resolution: '1.05 Å', holo: 234, afPlddt: 91, sites: 1, domains: 'Macro domain', disorder: '4%', cofactors: 'none annotated' },
    { names: ['kras', 'p01116'], accession: 'P01116', entry: 'RASK_HUMAN', label: 'KRAS', organism: 'Homo sapiens', length: 189, pdb: '6VJJ', resolution: '1.90 Å', holo: 312, afPlddt: 93, sites: 2, domains: 'Small GTPase', disorder: '8% (HVR)', cofactors: 'GDP · Mg²⁺' },
    { names: ['raf1', 'craf', 'raf', 'p04049'], accession: 'P04049', entry: 'RAF1_HUMAN', label: 'RAF1 RBD', organism: 'Homo sapiens', length: 648, pdb: '6VJJ', resolution: '1.90 Å', holo: 21, afPlddt: 74, sites: 1, domains: 'RBD · C1 · Protein kinase', disorder: '31%', cofactors: 'none annotated' },
    { names: ['egfr', 'p00533'], accession: 'P00533', entry: 'EGFR_HUMAN', label: 'EGFR kinase', organism: 'Homo sapiens', length: 1210, pdb: '1M17', resolution: '2.60 Å', holo: 198, afPlddt: 86, sites: 2, domains: 'Receptor L · Furin-like · Protein kinase', disorder: '15%', cofactors: 'Mg²⁺ · ATP site' },
    { names: ['hsp90', 'p07900'], accession: 'P07900', entry: 'HS90A_HUMAN', label: 'HSP90α', organism: 'Homo sapiens', length: 732, pdb: '2VCI', resolution: '1.90 Å', holo: 356, afPlddt: 85, sites: 1, domains: 'HATPase_c · HSP90', disorder: '11% (charged linker)', cofactors: 'ATP · Mg²⁺' },
  ],
  ligands: [
    { names: ['imatinib', 'gleevec', 'sti-571', 'sti571'], smiles: 'Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1', ccd: 'STI', cid: '5291', chembl: 'CHEMBL941', formula: 'C29H31N7O', mw: 493.6, inchikey: 'KTUFNOKKBVMGRW-UHFFFAOYSA-N', activities: 1842, stereo: 0, pka: 'piperazine 7.7' },
    { names: ['erlotinib'], smiles: 'COCCOc1cc2ncnc(Nc3cccc(C#C)c3)c2cc1OCCOC', ccd: 'AQ4', cid: '176870', chembl: 'CHEMBL553', formula: 'C22H23N3O4', mw: 393.4, inchikey: 'AAKJLRGGTJKAMG-UHFFFAOYSA-N', activities: 1203, stereo: 0, pka: 'quinazoline 5.4' },
    { names: ['adp-ribose', 'adpr'], smiles: 'Nc1ncnc2n(cnc12)C1OC(COP(O)(=O)OP(O)(=O)OCC2OC(O)C(O)C2O)C(O)C1O', ccd: 'APR', cid: '32014', chembl: '—', formula: 'C15H23N5O14P2', mw: 559.3, inchikey: 'SRNWOUGRCWSEMX-UHFFFAOYSA-N', activities: 0, stereo: 9, pka: 'phosphates 1.5, 6.4' },
  ],
};

export const CATALOG = ENTITIES;

// Entity resolution for the side panel: which sources to query for the names in `text`, and the
// mocked answers. `ms` is the simulated latency.
export function lookupEntities(text: string): EntityGroup[] {
  const t = (text || '').toLowerCase();
  const prots = ENTITIES.proteins.filter((p) => p.names.some((n) => t.includes(n)));
  const ligs = ENTITIES.ligands.filter((l) => l.names.some((n) => t.includes(n)));
  const out: EntityGroup[] = [];
  prots.forEach((p) => {
    out.push({ key: `uniprot:${p.accession}`, kind: 'protein', title: p.label, source: 'UniProt', query: p.accession, ms: 420, rows: [[p.entry, `${p.length.toLocaleString()} aa`], ['Organism', p.organism], ['Domains', p.domains], ['Cofactors', p.cofactors], ['Release', '2026_04']] });
    out.push({ key: `rcsb:${p.accession}`, kind: 'protein', title: p.label, source: 'RCSB PDB', query: p.pdb, ms: 640, rows: [['Holo entries', String(p.holo)], ['Reference', `${p.pdb} · ${p.resolution}`], ['SIFTS', 'mapped · 2026.09']] });
    out.push({ key: `afdb:${p.accession}`, kind: 'protein', title: p.label, source: 'AlphaFold DB', query: `AF-${p.accession}-F1`, ms: 820, rows: [['Mean pLDDT', String(p.afPlddt)], ['Disorder', p.disorder]] });
    out.push({ key: `pdbekb:${p.accession}`, kind: 'protein', title: p.label, source: 'PDBe-KB', query: p.accession, ms: 300, rows: [['Binding sites', String(p.sites)]] });
  });
  ligs.forEach((l) => {
    out.push({ key: `pubchem:${l.cid}`, kind: 'ligand', title: l.names[0], source: 'PubChem', query: `CID ${l.cid}`, ms: 520, rows: [['Formula', `${l.formula} · ${l.mw}`], ['InChIKey', l.inchikey], ['SMILES', l.smiles]] });
    out.push({ key: `ccd:${l.ccd}`, kind: 'ligand', title: l.names[0], source: 'PDB CCD', query: l.ccd, ms: 260, rows: [['Ideal geometry', 'present'], ['Stereocentres', String(l.stereo)]] });
    out.push({ key: `chembl:${l.chembl}`, kind: 'ligand', title: l.names[0], source: 'ChEMBL', query: l.chembl, ms: 700, rows: [['Activities', l.activities.toLocaleString()], ['pKa', l.pka]] });
  });
  return out;
}

export interface InterpretRunResult {
  task: string;
  tools: string[];
  target: string;
  partner: string;
  ligand: string;
  seeds: number;
  ph: number;
  reference: string;
  claim: string;
  steps: Step[];
}

export function interpretRun(text: string): InterpretRunResult {
  // Mocked interpreter. Returns settings plus the evidence (matched phrases) for each decision,
  // in the same shape a constrained LLM call would return: { field, value, because }.
  const t = text.toLowerCase();
  const steps: Step[] = [];
  let task = 'ligand_pose';
  if (/screen|library|enrich|decoy/.test(t)) task = 'virtual_screening';
  else if (/redock/.test(t)) task = 'redocking';
  else if (/blind/.test(t)) task = 'blind_docking';
  else if (/variant|mutant|mutation|resistan/.test(t)) task = 'variant_effect';
  else if (/design(ed)?\b|binder design|self-consisten/.test(t)) task = 'design_validation';
  else if (/monomer|fold of|structure of\b/.test(t) && !/complex|partner|ligand|dock/.test(t)) task = 'monomer';
  else if (/binding site|where does|which pocket|site identif/.test(t)) task = 'binding_site';
  else if (/rank|series|analog|congeneric|sar\b|affinit/.test(t)) task = 'affinity_ranking';
  else if (/pydock|haddock|protein.protein docking/.test(t)) task = 'protein_protein_docking';
  else if (/known complex|assembl|stoichiometr/.test(t)) task = 'known_complex';
  else if (/interact|partner|bind(s|ing)? to|complex with|discover/.test(t) && !/pocket|dock|pose|ligand/.test(t)) task = 'interaction_discovery';
  else if (/dock/.test(t) && !/boltz|protenix|alphafold|chai|co-?fold/.test(t)) task = 'pose_known_pocket';
  const taskWords = (t.match(/screen|redock|blind|variant|design|monomer|site|dock|pose|pocket|rank|series|analog|congeneric|interact|partner|discover|assembl|bind\w*/g) || []).slice(0, 3);
  steps.push({ field: 'task', value: task, because: taskWords.length ? `matched “${[...new Set(taskWords)].join('”, “')}”` : 'default for a ligand input' });

  const tools = TOOLS.filter((x) => t.includes(x.name.toLowerCase()) || t.includes(x.id)).map((x) => x.id);
  const taskDef = TASKS.find((x) => x.id === task) as Task;
  const chosenTools = tools.length ? tools : taskDef.defaultTools;
  steps.push({ field: 'tools', value: chosenTools, because: tools.length ? 'named in the request' : `task default: cross-family pair for ${taskDef.name.toLowerCase()}` });

  const prots = ENTITIES.proteins.filter((p) => p.names.some((n) => t.includes(n)));
  const accMatch = text.match(/\b[OPQ][0-9][A-Z0-9]{3}[0-9]\b|\b[A-NR-Z][0-9][A-Z][A-Z0-9]{2}[0-9]\b/);
  const target = prots[0] ? prots[0].accession : accMatch ? accMatch[0] : 'P00519';
  steps.push({ field: 'target', value: target, because: prots[0] ? `“${prots[0].label}” → UniProt ${target}` : accMatch ? 'accession given explicitly' : 'no target recognised; example target used' });
  if (task === 'interaction_discovery') {
    const partner = prots[1] ? prots[1].accession : 'P04049';
    steps.push({ field: 'partner', value: partner, because: prots[1] ? `“${prots[1].label}” → UniProt ${partner}` : 'no partner recognised; example partner used' });
  }
  const lig = ENTITIES.ligands.find((l) => l.names.some((n) => t.includes(n)));
  const smilesMatch = text.match(/[A-Za-z0-9@+\-[\]()\\/%=#$.]{12,}/g)?.find((s) => /[=#()[\]]/.test(s) && !/\s/.test(s));
  if (task !== 'interaction_discovery') {
    const ligand = lig ? lig.smiles : smilesMatch || ENTITIES.ligands[0].smiles;
    steps.push({ field: 'ligand', value: ligand, because: lig ? `“${lig.names[0]}” → CCD ${lig.ccd}, PubChem ${lig.cid}` : smilesMatch ? 'SMILES given explicitly, identity will be checked by InChIKey' : 'no ligand recognised; example ligand used' });
  }
  const seedMatch = t.match(/(\d+)\s*seeds?/);
  const seeds = seedMatch ? Math.min(20, Math.max(1, +seedMatch[1])) : 5;
  steps.push({ field: 'seeds', value: seeds, because: seedMatch ? 'stated in the request' : 'task default (five independent seeds, counted separately from diffusion samples)' });
  const phMatch = t.match(/ph\s*([\d.]+)/);
  const ph = phMatch ? +phMatch[1] : 7.4;
  steps.push({ field: 'ph', value: ph, because: phMatch ? 'stated in the request' : 'physiological default; protonation enumerated at this pH' });
  const pdbMatch = text.match(/\b[1-9][A-Za-z0-9]{3}\b/);
  const reference = (prots[0] && prots[0].pdb) || (pdbMatch ? pdbMatch[0].toUpperCase() : '1IEP');
  steps.push({ field: 'reference', value: reference, because: pdbMatch ? 'PDB entry named in the request' : `holo entry for the target from RCSB, used for redocking control` });
  steps.push({ field: 'claim', value: taskDef.claim, because: 'the only claim this task is permitted to support' });
  const partnerStep = steps.find((s) => s.field === 'partner');
  const ligandStep = steps.find((s) => s.field === 'ligand');
  return {
    task,
    tools: chosenTools,
    target,
    partner: partnerStep ? String(partnerStep.value) : '',
    ligand: ligandStep ? String(ligandStep.value) : '',
    seeds,
    ph,
    reference,
    claim: taskDef.claim,
    steps,
  };
}

// ---- Deterministic pseudo-random for stable mock values ----
type Rng = () => number;
function rng(seed: number): Rng {
  let s = seed >>> 0 || 1;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}
const hex = (r: Rng, n = 64) => Array.from({ length: n }, () => '0123456789abcdef'[Math.floor(r() * 16)]).join('');

/** Form passed to makeRunRecord (prototype `form`). */
export interface MockForm {
  task: string;
  tools: string[];
  target: string;
  ligand?: string;
  partner?: string;
  reference: string;
  ph: number;
  seeds: number;
  name?: string;
}

interface F extends MockForm {
  realTask: string;
  claim: string;
  createdAt: number;
  ccd?: string;
  cid?: string;
  chembl?: string;
  primary: string;
  secondary: string;
  dockName: string | null;
  // additions: register ids behind the display names, so metrics can reference output keys
  primaryId: string | null;
  secondaryId: string | null;
  dockId: string | null;
}

function sources(f: F, r: Rng): RecordSource[] {
  const retrieved = (i: number) => new Date(f.createdAt + i * 310).toISOString();
  const S: Omit<RecordSource, 'retrievedAt'>[] = [
    { source: 'UniProt', supplies: 'Canonical sequence, PTMs, active site', accession: f.target, release: '2026_04', version: 'seq v2', sha256: hex(r), cached: false, ms: 212 },
    { source: 'RCSB PDB', supplies: 'Experimental structure, bound ligand', accession: f.reference, release: 'rev 1.3', version: 'mmCIF', sha256: hex(r), cached: true, ms: 48 },
    { source: 'SIFTS', supplies: 'PDB↔UniProt residue mapping', accession: `${f.reference}/${f.target}`, release: '2026.09', version: '', sha256: hex(r), cached: true, ms: 31 },
    { source: 'AlphaFold DB', supplies: 'Predicted structure, pLDDT, PAE', accession: `AF-${f.target}-F1`, release: 'v4', version: 'model v4', sha256: hex(r), cached: false, ms: 388 },
    { source: 'PDBe-KB', supplies: 'Known binding sites', accession: f.target, release: '2026.3', version: '', sha256: hex(r), cached: true, ms: 27 },
    { source: 'PLINDER', supplies: 'Exposure table', accession: f.reference, release: '2024-06', version: 'v2', sha256: hex(r), cached: true, ms: 19 },
    { source: 'MMseqs2 · ColabFoldDB', supplies: 'Multiple sequence alignment', accession: `query ${hex(r, 8)}`, release: 'snapshot 2025-11', version: 'MMseqs2 15', sha256: hex(r), cached: true, ms: 64 },
  ];
  if (f.task !== 'interaction_discovery') {
    S.push({ source: 'PDB CCD', supplies: 'Ligand definition, ideal geometry', accession: f.ccd || 'STI', release: '2026-09-30', version: '', sha256: hex(r), cached: true, ms: 22 });
    S.push({ source: 'PubChem', supplies: 'Ligand identity (InChIKey)', accession: `CID ${f.cid || '5291'}`, release: '2026-10', version: '', sha256: hex(r), cached: false, ms: 301 });
    S.push({ source: 'ChEMBL', supplies: 'Bioactivities, actives, inactives', accession: f.chembl || 'CHEMBL941', release: 'ChEMBL 35', version: '', sha256: hex(r), cached: false, ms: 276 });
  } else {
    S.push({ source: 'UniProt', supplies: 'Partner sequence', accession: f.partner || '', release: '2026_04', version: 'seq v1', sha256: hex(r), cached: false, ms: 198 });
    S.push({ source: 'STRING · IntAct', supplies: 'Known partners, decoy candidates', accession: f.target, release: 'v12.0 · 2026-08', version: 'evidence: experiments', sha256: hex(r), cached: true, ms: 44 });
    S.push({ source: 'InterPro · Pfam', supplies: 'Domain boundaries', accession: f.target, release: '103.0', version: '', sha256: hex(r), cached: true, ms: 25 });
  }
  return S.map((s, i) => ({ ...s, retrievedAt: retrieved(i) }));
}

let msSeed = 11;
const C = (id: string, name: string, tool: string, gate: UiCheck['gate'], result: Result, evidence: string): UiCheck => {
  msSeed = (msSeed * 1664525 + 1013904223) >>> 0;
  return { id, name, tool, gate, result, evidence, ms: 18 + (msSeed % 880) };
};

/** Reset module-level counters so a seeded mock session is reproducible. */
export function resetMockCounters(): void {
  msSeed = 11;
  counter = 0;
}

// Key figures per layer for the report sidebar (concrete values, not pass/warn).
function layerFigures(f: F): [string, string][][] {
  const lig = f.task !== 'interaction_discovery';
  return [
    [['objects fetched', lig ? '10' : '10'], ['cache hits', lig ? '6' : '7'], ['network', lig ? '4' : '3'], ['sequence mismatches', '0'], ['InChIKey match', lig ? 'yes' : '—'], ['releases pinned', 'all']],
    [['manifest ↔ source', 'checksums equal'], ['truncations', '0'], ['substitutions', '0'], ['MSA query hash', 'matches'], ['stoichiometry', lig ? 'A1 + ligand' : 'A1 : B1'], ['outputs reconciled', `${f.seeds * 2}`]],
    lig ? [['Neff/L', '9.4'], ['distinct sequences', '2,318'], ['pocket volume', '612 Å³'], ['missing pocket residues', '0'], ['receptor state', 'holo · open'], ['ligand protonation states', '2'], ['docking box', '24 × 22 × 26 Å']]
      : [['Neff/L', '9.4'], ['paired depth', '11 seq'], ['paralog rows', '38%'], ['cofactors', 'GDP · Mg²⁺'], ['interface disorder', '0%']],
    lig ? [['training cutoff', '2023-06-01'], ['pocket similarity', '71 (SuCOS×cov)'], ['ligand analogues', '14 systems'], ['sequence identity', '100%'], ['templates', 'off'], ['token count', '1,163 / 1,536']]
      : [['training cutoff', '2023-06-01'], ['pocket similarity', '34'], ['sequence identity', '100%'], ['templates', 'off'], ['token count', '269 / 1,536']],
    lig ? [['PoseBusters', '20/20'], ['min. protein distance', '2.9 Å'], ['volume overlap', '0.02'], ['unlikely torsions', '0'], ['minimisation drift', '0.6 Å'], ['unsatisfied polars', '1'], ['hydrophobic complementarity', '81%'], ['known interactions', '11/11'], ['clashscore', '3.1']]
      : [['clashscore', '3.1'], ['Ramachandran outliers', '0'], ['buried area', '1,240 Å²'], ['shape complementarity', '0.68'], ['salt bridges', '3'], ['buried charges', '0'], ['Switch II state', 'not in PDB']],
    lig ? [['pocket pLDDT', '91'], ['pocket PAE', '3.2 Å'], ['ipTM', '0.88'], ['medoid cluster', `${f.seeds - 1}/${f.seeds}`], ['Kendall τ', '0.90'], ['Boltz-2 vs Gnina', '1.1 Å'], ['redocking RMSD', '0.8 Å']]
      : [['interface pLDDT', '84'], ['interface PAE', '9.8 Å'], ['ipTM', '0.71'], ['pDockQ', '0.46'], ['medoid cluster', `3/${f.seeds}`], ['DockQ vs Protenix', '0.41'], ['decoy partners', '6/12']],
  ];
}

// Short key figures per layer, shown in the report sidebar.
function layerSummary(f: F): string[][] {
  const lig = f.task !== 'interaction_discovery';
  return lig
    ? [
        ['10 objects', '6 cached', '0 mismatches'], ['checksums agree', `${f.seeds * 2} outputs`], ['Neff/L 9.4', 'pocket 612 Å³', '2 protomers'],
        ['exposure 71', 'cutoff 2023-06'], ['PoseBusters 20/20', 'drift 0.6 Å', '1 unsat. N–H'], [`${f.seeds - 1}/${f.seeds} in cluster`, 'τ 0.90', 'redock 0.8 Å'],
      ]
    : [
        ['10 objects', '7 cached', '0 mismatches'], ['checksums agree', `${f.seeds * 2} outputs`], ['Neff/L 9.4', 'paired 11 seq', 'paralogs 38%'],
        ['exposure 34', 'cutoff 2023-06'], ['BSA 1,240 Å²', 'Sc 0.68', 'Switch II novel'], ['3/5 in cluster', 'ipTM 0.71', 'decoys 6/12'],
      ];
}

function layerChecks(f: F): UiCheck[][] {
  const lig = f.task !== 'interaction_discovery';
  const disc = f.task === 'interaction_discovery';
  const aff = f.task === 'affinity_ranking';
  return [
    [
      C('src.uniprot_pdb_agreement', 'UniProt sequence agrees with PDB SEQRES through SIFTS', 'SIFTS mapping', 'Stop', 'pass', `${f.target} ↔ ${f.reference} chain A, 0 mismatches over mapped residues`),
      ...(lig ? [C('src.ligand_identity', 'Ligand SMILES matches CCD record by InChIKey', 'RDKit InChIKey', 'Stop', 'pass', `InChIKey agrees with CCD ${f.ccd || 'STI'} and PubChem CID ${f.cid || '5291'}`)] : []),
      C('src.cache_policy', 'No silent fallback to network or different release', 'Content-addressed cache', 'Stop', 'pass', `${lig ? 10 : 10} fetches, ${lig ? 6 : 7} cache hits, all releases pinned`),
    ],
    [
      C('ppi.input.integrity', 'Sequence in the run matches the manifest and source record', 'Harness', 'Stop', 'pass', 'Manifest checksum equals source checksum'),
      C('ppi.input.integrity.truncation', 'No silent truncation or substitution of residues', 'Harness', 'Stop', 'pass', `${disc ? 2 : 1} chain${disc ? 's' : ''}, full length, 0 substitutions`),
      C('ppi.msa.integrity', 'MSA belongs to the paired chain, no cache collision', 'Harness', 'Stop', 'pass', 'Query hash matches alignment header'),
      ...(lig
        ? [
            C('rdkit.sanitise', 'Ligand parses, valences correct, charges sane', 'RDKit sanitisation', 'Stop', 'pass', 'Sanitised, formal charge +0 at neutral form'),
            C('rdkit.stereo', 'Stereocentres and double-bond geometry explicitly defined', 'RDKit stereo perception', 'Warn', aff ? 'warn' : 'pass', aff ? '2 of 12 series members have one undefined stereocentre' : 'No undefined stereocentres'),
          ]
        : []),
      C('ppi.context.composition', 'Chain composition and stoichiometry match the declared assembly', 'Harness', 'Stop', 'pass', disc ? 'A1 : B1 as declared' : 'A1 + ligand as declared'),
      C('ppi.provenance.consistency', 'Model version, checkpoint and database snapshot consistent', 'Harness', 'Stop', 'pass', `${f.primary} · checkpoint pinned · ColabFoldDB 2025-11`),
      C('ppi.output.reconciliation', 'Expected outputs present, no duplicates, no stale files', 'Harness', 'Stop', 'pass', `${f.seeds} seeds × ${lig ? 2 : 2} executors, ${f.seeds * 2} outputs reconciled`),
    ],
    [
      C('ppi.msa.depth', 'Alignment depth, distinct sequences and Neff/L', 'Harness · MMseqs2', 'Warn', 'pass', `Neff/L 9.4, 2,318 distinct sequences`),
      ...(disc
        ? [
            C('ppi.msa.pairing', 'Paired alignment depth for the complex', 'Harness', 'Stop', 'stop', 'Paired depth 11 sequences, below the 32 required for interaction discovery'),
            C('ppi.msa.paralog', 'Paralog ambiguity in pairing', 'Harness', 'Warn', 'warn', 'RAF family paralogs present in 38% of paired rows'),
          ]
        : []),
      C('ppi.context.requirements', 'Required cofactors, ions, nucleic acids present', 'Harness · UniProt · PDBe-KB', 'Stop', 'pass', disc ? 'GDP and Mg²⁺ declared for KRAS' : 'No required cofactor annotated for this pocket'),
      C('disorder.region', 'Disorder in the region of interest', 'MobiDB · DisProt · AF pLDDT', 'Warn', 'pass', 'Pocket residues ordered, mean AF pLDDT 93'),
      ...(lig
        ? [
            C('pocket.complete', 'Pocket residues resolved, no missing loops', 'Gemmi · PDBFixer', 'Stop', 'pass', '0 missing residues within 8 Å of the ligand'),
            C('receptor.state', 'Receptor state apo or holo, pocket open', 'PDB metadata · fpocket', 'Warn', 'pass', `Holo entry ${f.reference}, pocket volume 612 Å³`),
            C('receptor.protonation', `Receptor protonation at pH ${f.ph}`, 'PROPKA · PDB2PQR', 'Warn', 'pass', '3 His assigned, 1 flipped'),
            C('ligand.protonation', `Ligand protonation and tautomer at pH ${f.ph}`, 'Dimorphite-DL · RDKit', 'Warn', 'warn', 'Two plausible states (piperazine N-methyl pKa 7.7), both enumerated'),
            C('docking.box', 'Docking box encloses the pocket with margin', 'Box from crystal ligand', 'Stop', 'pass', '24 × 22 × 26 Å, 4 Å margin, all pocket residues enclosed'),
          ]
        : []),
    ],
    [
      C('ppi.provenance.model_db_config', 'Model training cutoff recorded', 'Model registry', 'Stop', 'pass', `${f.primary} cutoff 2023-06-01${f.dockName ? ' · ' + f.dockName + ' physics-based for pose' : ''}`),
      C('exposure.pocket', 'Pocket-level similarity to pre-cutoff complexes (SuCOS × coverage)', 'PLINDER · Foldseek', 'Warn', lig ? 'warn' : 'pass', lig ? `Similarity 71 to ${f.reference} (pre-cutoff): this is likely recall, not generalisation` : 'Similarity 34, below the 50 threshold'),
      ...(lig ? [C('exposure.ligand', 'Ligand prevalence (>0.9 Tanimoto in >100 training systems)', 'RDKit fingerprints', 'Warn', 'pass', '14 analogues in training systems')] : []),
      C('exposure.sequence', 'Chain identity to pre-cutoff complexes (secondary)', 'MMseqs2', 'Reported', 'reported', '100% identity; reported, never used alone'),
      C('template.use', 'Template use distinguished from training exposure', 'Template hits', 'Warn', 'pass', 'Templates disabled for this run'),
      C('ppi.regime.applicability', 'Modality inside the validated set', 'Harness · TMbed', 'Warn', 'pass', 'Soluble kinase domain, no metal site, no covalent bond'),
      C('ppi.metric.endpoint', 'Endpoint fits the tool', 'Harness', 'Stop', 'pass', aff ? 'Boltz-2 affinity read as relative ranking only' : 'No affinity read from interface confidence'),
      C('kit.accelerated', 'Accelerated mode verified against stock on this hardware', 'Kit ACTIVE line', 'Warn', 'pass', 'ACTIVE: stock kernels'),
    ],
    [
      ...(lig
        ? [
            C('posebusters.geometry', 'Ligand bond lengths, angles, planarity, ring geometry', 'PoseBusters', 'Stop', 'pass', '20 of 20 tests pass for medoid pose'),
            C('posebusters.stereo', 'Stereochemistry preserved from input to output', 'PoseBusters', 'Stop', 'pass', 'All stereocentres preserved'),
            C('posebusters.clash', 'Protein–ligand clashes, volume overlap', 'PoseBusters', 'Stop', 'pass', 'Min distance 2.9 Å, overlap 0.02'),
            C('torsion.strain', 'Torsional strain against knowledge-based library', 'RDKit torsion rules', 'Warn', 'pass', '0 unlikely torsions'),
            C('minimisation.drift', 'Pose stability under restrained minimisation', 'OpenMM · AMBER · OpenFF', 'Warn', aff ? 'warn' : 'pass', aff ? '2 of 12 members drift 2.3 Å' : 'Drift 0.6 Å'),
            C('chem.unsatisfied', 'Buried polar atoms with no hydrogen-bond partner', 'FreeSASA · PLIP', 'Warn', 'warn', '1 unsatisfied buried N–H (amide NH, 4.1 Å from Glu286)'),
            C('chem.complementarity', 'Hydrophobic complementarity', 'FreeSASA · RDKit', 'Warn', 'pass', '81% buried nonpolar surface against nonpolar pocket'),
            C('chem.known_binders', 'Fingerprint similarity to known binders in the same pocket', 'ProLIF · PDBe-KB', 'Warn', 'pass', 'Reproduces hinge Met318 H-bond and Glu286 salt bridge seen in 11 of 11 entries'),
          ]
        : [
            C('molprobity', 'Clashscore, Ramachandran, rotamers, Cβ deviations', 'Harness geometry (Phenix absent)', 'Warn', 'pass', 'Clashscore 3.1, 0 Ramachandran outliers'),
            C('ppi.structure.topology', 'Chains topologically entangled', 'Harness', 'Stop', 'pass', 'No entanglement'),
            C('interface.area', 'Interface buried area, contacts, salt bridges', 'AlphaJudge · FreeSASA', 'Warn', 'pass', 'BSA 1,240 Å², 3 salt bridges'),
            C('interface.shape', 'Shape complementarity', 'AlphaJudge', 'Warn', 'pass', 'Sc 0.68'),
            C('chem.buried_charge', 'Charged group buried in hydrophobic environment', 'FreeSASA · PROPKA', 'Warn', 'pass', 'None'),
            C('receptor.conformational_state', 'Receptor state against known states of the target', 'Superposition · PDBe-KB', 'Warn', 'warn', 'Switch II in a state not observed experimentally for GDP-bound KRAS'),
          ]),
    ],
    [
      C('metric.local_plddt', 'pLDDT restricted to pocket or interface residues', 'Boltz-2', 'Reported', 'reported', lig ? 'Pocket pLDDT 91 (global 88 not substituted)' : 'Interface pLDDT 84'),
      C('metric.interface_pae', 'PAE across the pocket or interface block', 'Boltz-2', 'Reported', 'reported', lig ? 'Pocket PAE 3.2 Å' : 'Interface PAE 9.8 Å'),
      C('ppi.metric.length_confound', 'ipTM partner-length confound', 'Harness', 'Warn', disc ? 'warn' : 'pass', disc ? 'ipTM 0.71 within the range explained by partner length for 80-residue RBDs' : 'Not applicable to a small-molecule partner'),
      C('ppi.metric.threshold_provenance', 'Confidence threshold origin and prevalence', 'Harness', 'Warn', 'warn', `${f.primary} pose threshold borrowed from Runs N’ Poses benchmark, not yet recalibrated on this target`),
      C('ppi.execution.replicate_stability', 'Independent seeds counted separately from samples', 'Harness', 'Stop', 'pass', `${f.seeds} seeds × 5 diffusion samples`),
      C('ppi.execution.replicate_identity', 'No duplicated run presented as a replicate', 'Harness', 'Stop', 'pass', 'All seed outputs distinct by checksum'),
      C('cluster.medoid', 'Representative pose is the medoid of the largest cluster', 'spyrmsd', 'Reported', 'reported', lig ? `Cluster 1 holds ${f.seeds - 1} of ${f.seeds} seeds` : `Cluster 1 holds 3 of ${f.seeds} seeds`),
      C('ppi.execution.ranking_stability', 'Ranking stability across seeds (Kendall τ)', 'Harness', 'Warn', aff ? 'pass' : 'pass', aff ? 'τ = 0.82 across seeds' : 'τ = 0.9'),
      C('agreement.cross_family', 'Agreement between independent methods', 'spyrmsd · DockQ', 'Reported', 'reported', lig ? `${f.primary} medoid vs ${f.secondary} top pose 1.1 Å` : `${f.primary} vs ${f.secondary} DockQ 0.41 (shared training data, moderate weight)`),
      C('controls.required', 'Controls the claim requires were run and are sound', 'Harness controls', 'Stop', disc ? 'stop' : 'pass', disc ? 'Decoy panel incomplete: 6 of 12 non-cognate partners, paralogs absent' : lig ? `Redocking control reproduced the crystal pose (${aff ? '0.9' : '0.8'} Å)` : ''),
    ],
  ];
}

function verdictFor(f: F, layers: UiCheck[][]): Verdict {
  const all = layers.flat();
  const stops = all.filter((c) => c.result === 'stop');
  const warns = all.filter((c) => c.result === 'warn');
  const outcome = stops.length ? 'refused' : warns.length ? 'narrowed' : 'supported';
  const statement =
    outcome === 'refused'
      ? `The claim “${f.claim}” cannot be reported. ${stops.length} check${stops.length > 1 ? 's' : ''} stopped the run; see Layer ${LAYERS[layers.findIndex((l) => l.some((c) => c.result === 'stop'))].i}.`
      : outcome === 'narrowed'
        ? `The result supports “${f.claim}” with ${warns.length} qualification${warns.length > 1 ? 's' : ''}. Training exposure and threshold provenance narrow what this demonstrates about generalisation.`
        : `The result supports “${f.claim}”. No check warned or stopped; absence of a detected failure is not evidence of accuracy.`;
  return { claim: f.claim, outcome, statement, stops: stops.map((c) => c.id), warnings: warns.map((c) => c.id) };
}

// addition: register helpers, so mock metrics reference ToolOutput keys
function toolOutputs(id: string | null): ToolOutput[] {
  return (id && TOOLS.find((t) => t.id === id)?.outputs) || [];
}
function hasOutput(id: string | null, key: string): boolean {
  return toolOutputs(id).some((o) => o.key === key);
}
function firstOutput(id: string | null, pred: (o: ToolOutput) => boolean): string | undefined {
  return toolOutputs(id).find(pred)?.key;
}

function stats(f: F, r: Rng): UiStats {
  const lig = f.task !== 'interaction_discovery';
  const seeds: (SeedStat & { confidence: number })[] = Array.from({ length: f.seeds }, (_, i) => {
    const rmsd = lig ? (i === f.seeds - 1 ? 2.6 + r() * 0.8 : 0.3 + r() * 0.9) : i < 3 ? 1.1 + r() * 1.5 : 4.8 + r() * 3.2;
    return { seed: 1000 + i * 17, rmsdToMedoid: +rmsd.toFixed(2), cluster: rmsd < 2 ? 1 : 2, confidence: +(lig ? 0.86 + r() * 0.1 : 0.62 + r() * 0.16).toFixed(2) };
  });
  const methods = lig ? [f.primary, f.secondary, 'Crystal'] : [f.primary, f.secondary, f.dockName || 'pyDock'];
  const vals = lig ? [[0, 1.1, 0.9], [1.1, 0, 1.4], [0.9, 1.4, 0]] : [[0, 3.8, 7.2], [3.8, 0, 6.9], [7.2, 6.9, 0]];
  const agreement: AgreementRow[] = methods.map((a, i) => ({ method: a, cells: methods.map((b, j) => ({ vs: b, value: vals[i][j], unit: lig ? 'Å' : 'Å iRMSD', weight: i === j ? '—' : lig ? (i === 2 || j === 2 ? 'decisive' : 'high') : j === 2 || i === 2 ? 'high' : 'moderate' })) }));
  const perturbation: PerturbationRow[] = lig
    ? [
        { name: 'Contact removal', construction: 'Side chains within 3.5 Å → Gly', expected: 'Ligand displaced', observed: 'Displaced 6.8 Å', ok: true },
        { name: 'Overpacking', construction: 'Same residues → Phe', expected: 'Displaced or clashes', observed: '3 clashes reported', ok: true },
        { name: 'Chemical inversion', construction: 'Miyata-distant substitutions', expected: 'Ligand displaced', observed: 'Pose retained (0.9 Å)', ok: false },
        { name: 'Ligand modification', construction: 'Hydroxyl methylation', expected: 'Binding weakened', observed: 'Confidence −0.21', ok: true },
        { name: 'Apo control', construction: 'Mutated receptor without ligand', expected: 'Fold unchanged', observed: 'Cα RMSD 0.7 Å', ok: true },
      ]
    : [];
  const calibration = Array.from({ length: 8 }, (_, i) => ({ x: +(0.5 + i * 0.07).toFixed(2), passed: +(0.42 + i * 0.065 + r() * 0.03).toFixed(2), flagged: +(0.18 + i * 0.045 + r() * 0.03).toFixed(2) }));
  const pid = f.primaryId;
  const did = f.dockId;
  const key = (id: string | null, k: string) => (hasOutput(id, k) ? { toolId: id as string, key: k } : {});
  const dockPoseKey = firstOutput(did, (o) => !o.rankingOnly && (o.kind === 'score' || o.kind === 'confidence'));
  const dockAffKey = firstOutput(did, (o) => !!o.rankingOnly);
  const metrics: UiMetric[] = lig
    ? [
        { name: 'Pocket pLDDT', value: '91', read: 'Local structural confidence', tool: f.primary },
        { name: 'Pocket PAE', value: '3.2 Å', read: 'Relative placement confidence', tool: f.primary },
        { name: 'ipTM', value: '0.88', read: 'Interface confidence', tool: f.primary, ...key(pid, 'iptm') },
        { name: 'pTM', value: '0.93', read: 'Fold confidence', tool: f.primary, ...key(pid, 'ptm') },
        { name: 'pDockQ (Bryant 2022)', value: '0.71', read: 'Interface quality estimate', tool: 'AlphaJudge' },
        { name: 'pDockQ2', value: '0.68', read: 'Interface quality estimate', tool: 'AlphaJudge' },
        { name: 'ipSAE', value: '0.74', read: 'Interface quality estimate', tool: 'Harness adapter' },
        { name: 'LIS', value: '0.52', read: 'Local interaction score', tool: 'Harness adapter' },
        { name: 'PoseBusters', value: '20 / 20', read: 'Physical validity', tool: 'PoseBusters' },
        ...(f.dockName
          ? [
              { name: `${f.dockName} pose score`, value: /gnina/i.test(f.dockName) ? '0.79 CNN' : /diffdock/i.test(f.dockName) ? '0.71 conf.' : '−10.2 kcal/mol', read: 'Pose plausibility, beside PoseBusters', tool: f.dockName, ...(dockPoseKey ? { toolId: did as string, key: dockPoseKey } : {}) },
              { name: `${f.dockName} affinity score`, value: /gnina/i.test(f.dockName) ? '6.4 pK' : '−10.2 kcal/mol', read: 'Ranking within this run only', tool: f.dockName, separate: true, ...(dockAffKey ? { toolId: did as string, key: dockAffKey } : {}) },
            ]
          : []),
        { name: `${f.primary} affinity`, value: f.task === 'affinity_ranking' ? 'rank 1 of 12' : '6.9 log', read: 'Relative ranking only, never pose quality', tool: f.primary, separate: true, ...key(pid, 'affinity_pred_value') },
      ]
    : [
        { name: 'Interface pLDDT', value: '84', read: 'Local structural confidence', tool: f.primary, ...key(pid, 'complex_iplddt') },
        { name: 'Interface PAE', value: '9.8 Å', read: 'Relative placement confidence', tool: f.primary, ...key(pid, 'complex_ipde') },
        { name: 'ipTM', value: '0.71', read: 'Interface confidence, length-confounded', tool: f.primary, ...key(pid, 'iptm') },
        { name: 'pTM', value: '0.88', read: 'Fold confidence', tool: f.primary, ...key(pid, 'ptm') },
        { name: 'pDockQ (Bryant 2022)', value: '0.46', read: 'Interface quality estimate', tool: 'AlphaJudge' },
        { name: 'pDockQ2', value: '0.39', read: 'Interface quality estimate', tool: 'AlphaJudge' },
        { name: 'ipSAE', value: '0.52', read: 'Interface quality estimate', tool: 'Harness adapter' },
        { name: 'LIS', value: '0.31', read: 'Local interaction score', tool: 'Harness adapter' },
        { name: `DockQ vs ${f.secondary}`, value: '0.41', read: 'Cross-model agreement', tool: 'DockQ' },
        ...(f.dockName ? [{ name: `${f.dockName} energy`, value: '−28.4', read: 'Ranking within this run only', tool: f.dockName, separate: true, ...(dockAffKey ? { toolId: did as string, key: dockAffKey } : {}) }] : []),
      ];
  const PB_TESTS = ['mol_pred_loaded', 'sanitization', 'inchi_convertible', 'all_atoms_connected', 'molecular_formula', 'molecular_bonds', 'double_bond_stereochemistry', 'tetrahedral_chirality', 'bond_lengths', 'bond_angles', 'internal_steric_clash', 'aromatic_ring_flatness', 'double_bond_flatness', 'internal_energy', 'protein_ligand_maximum_distance', 'minimum_distance_to_protein', 'minimum_distance_to_organic_cofactors', 'minimum_distance_to_inorganic_cofactors', 'minimum_distance_to_waters', 'volume_overlap_with_protein'];
  const pbValues: Record<string, string> = { bond_lengths: '0 outliers', bond_angles: '0 outliers', internal_steric_clash: '0', internal_energy: '1.9× ratio', minimum_distance_to_protein: '2.9 Å', volume_overlap_with_protein: '0.02', aromatic_ring_flatness: '0.03 Å', tetrahedral_chirality: 'preserved' };
  const posebusters: PoseBustersTest[] = lig ? PB_TESTS.map((t) => ({ test: t, pass: true, value: pbValues[t] || 'ok' })) : [];
  const physics: PhysicsRow[] = seeds.map((s) => ({ seed: s.seed, drift: +(s.rmsdToMedoid < 2 ? 0.4 + r() * 0.5 : 1.8 + r() * 0.9).toFixed(2), torsions: s.rmsdToMedoid < 2 ? 0 : 1, clashes: 0, strain: +(3.1 + r() * 4).toFixed(1), unsatisfied: s.rmsdToMedoid < 2 ? 1 : 2, pbPassed: lig ? (s.rmsdToMedoid < 2 ? 20 : 18) : null, clashscore: +(2.4 + r() * 1.6).toFixed(1), rama: 0 }));
  const site: [string, string][] = lig
    ? [['pocket residues', '38'], ['pocket volume', '612 Å³ · fpocket'], ['P2Rank', 'rank 1 · 24.1'], ['druggability', '0.82'], ['ligand burial', '86% SASA'], ['placement', `${f.seeds}/${f.seeds} seeds · ≤4 Å of crystal centroid`]]
    : [['interface residues', '24 + 19'], ['buried area', '1,240 Å²'], ['shape complementarity', '0.68'], ['salt bridges', '3'], ['hydrogen bonds', '9'], ['placement', `3/${f.seeds} seeds · Switch I`]];
  const pose: [string, string][] = lig
    ? [['RMSD to crystal', '0.9 Å'], ['cluster 1', `${f.seeds - 1}/${f.seeds} seeds`], ['minimisation drift', '0.6 Å'], ['unlikely torsions', '0'], ['unsatisfied polars', '1 · amide N–H'], ['hinge H-bond', 'Met318 · 2.9 Å']]
    : [['iRMSD to Protenix', '3.8 Å'], ['cluster 1', `3/${f.seeds} seeds`], ['DockQ', '0.41'], ['Switch II state', 'not in PDB'], ['clashscore', '3.1'], ['Ramachandran outliers', '0']];
  const interactions: InteractionRow[] = lig
    ? [
        { residue: 'Met318', type: 'H-bond', distance: 2.9, known: true }, { residue: 'Glu286', type: 'Salt bridge', distance: 3.1, known: true }, { residue: 'Thr315', type: 'H-bond', distance: 3.0, known: true },
        { residue: 'Asp381', type: 'H-bond', distance: 2.8, known: true }, { residue: 'Ile360', type: 'Hydrophobic', distance: 3.8, known: false }, { residue: 'His361', type: 'Hydrophobic', distance: 3.9, known: true },
        { residue: 'Phe382', type: 'π stacking', distance: 3.7, known: true }, { residue: 'Leu248', type: 'Hydrophobic', distance: 4.0, known: false }, { residue: 'Val256', type: 'Hydrophobic', distance: 3.9, known: true },
      ]
    : [
        { residue: 'Arg41', type: 'Salt bridge', distance: 3.0, known: true }, { residue: 'Arg89', type: 'Salt bridge', distance: 2.9, known: true }, { residue: 'Gln66', type: 'H-bond', distance: 3.1, known: false },
        { residue: 'Asn71', type: 'H-bond', distance: 3.0, known: true }, { residue: 'Val69', type: 'Hydrophobic', distance: 3.9, known: true }, { residue: 'Thr68', type: 'H-bond', distance: 3.2, known: false },
      ];
  const medoidIdx = 0;
  const secId = f.secondaryId;
  const secScoreKey = firstOutput(secId, (o) => !o.rankingOnly && (o.kind === 'score' || o.kind === 'confidence')) || firstOutput(secId, () => true);
  const ensemble: EnsembleEntry[] = [
    { id: 'crystal', label: f.reference, kind: 'crystal', source: 'RCSB', rmsdToMedoid: lig ? 0.9 : 3.2, pocketPlddt: null, iptm: null, posebusters: null, cluster: null },
    ...seeds.map((s, i): EnsembleEntry => ({ id: `seed_${s.seed}`, label: `s${s.seed}`, kind: i === medoidIdx ? 'medoid' : 'seed', source: f.primary, rmsdToMedoid: i === medoidIdx ? 0 : s.rmsdToMedoid, pocketPlddt: Math.round((lig ? 86 : 78) + s.confidence * 8), iptm: +s.confidence.toFixed(2), posebusters: lig ? (s.rmsdToMedoid < 2 ? 20 : 18) : null, cluster: s.cluster, ...(pid ? { toolId: pid, values: hasOutput(pid, 'iptm') ? { iptm: +s.confidence.toFixed(2) } : {} } : {}) })),
    ...(lig
      ? [1, 2, 3].map((k): EnsembleEntry => {
          const cnn = +(0.79 - (k - 1) * 0.14).toFixed(2);
          return { id: `gnina_${k}`, label: `${f.secondary} ${k}`, kind: 'docking', source: f.secondary, rmsdToMedoid: +(1.1 + (k - 1) * 1.7 + r() * 0.4).toFixed(2), pocketPlddt: null, iptm: null, cnn, posebusters: 20 - (k - 1) * 2, cluster: k === 1 ? 1 : 2, ...(secId ? { toolId: secId, values: secScoreKey ? { [secScoreKey]: cnn } : {} } : {}) };
        })
      : [{ id: 'protenix_1', label: f.secondary, kind: 'model' as const, source: f.secondary, rmsdToMedoid: 3.8, pocketPlddt: 81, iptm: 0.66, posebusters: null, cluster: 2, ...(secId ? { toolId: secId, values: hasOutput(secId, 'iptm') ? { iptm: 0.66 } : {} } : {}) }]),
  ];
  const pair = seeds.map((s) => s.rmsdToMedoid).sort((a, b) => a - b);
  const pairwise = { median: pair[Math.floor(pair.length / 2)], iqr: [pair[Math.floor(pair.length / 4)], pair[Math.floor((pair.length * 3) / 4)]] as [number, number], ci95: [Math.max(0, pair[Math.floor(pair.length / 2)] - 0.4), pair[Math.floor(pair.length / 2)] + 0.6] as [number, number], n: f.seeds };
  const roc = f.task === 'affinity_ranking' ? Array.from({ length: 11 }, (_, i) => ({ fpr: i / 10, tpr: Math.min(1, +Math.pow(i / 10, 0.45).toFixed(2)) })) : null;
  return { seeds, agreement, perturbation, calibration, metrics, interactions, ensemble, pairwise, roc, posebusters, physics, site, pose, auc: roc ? 0.81 : null, enrichment: roc ? 'EF1% 8.4' : null, sitePlacement: lig ? '5 of 5 seeds in the crystal pocket' : '3 of 5 seeds at the Switch I interface', poseAccuracy: lig ? '4 of 5 seeds within 2 Å of the medoid' : '2 of 5 seeds within 2 Å iRMSD of the medoid' };
}

function narrate(f: F, layers: UiCheck[][], verdict: Verdict): string[] {
  const count = (i: number, res: Result) => layers[i].filter((c) => c.result === res).length;
  const s = (i: number) => `${layers[i].length} checks, ${count(i, 'pass')} passed${count(i, 'warn') ? `, ${count(i, 'warn')} warned` : ''}${count(i, 'stop') ? `, ${count(i, 'stop')} stopped` : ''}`;
  const lig = f.task !== 'interaction_discovery';
  return [
    `Layer 0 fetched every input from a named source and recorded accession, release, retrieval time and SHA-256. The UniProt sequence for ${f.target} agreed with the ${f.reference} SEQRES through SIFTS${lig ? ', and the ligand SMILES matched its CCD record by InChIKey' : ''}. ${s(0)}.`,
    `Layer 1 confirmed the run received what was declared: sequence and manifest checksums agree, the alignment belongs to its chain, stoichiometry matches the declared assembly and all ${f.seeds * 2} outputs reconciled. ${s(1)}.`,
    `Layer 2 found the alignment deep (Neff/L 9.4)${lig ? ` and the pocket complete and open in the holo entry. Two ligand protonation states are plausible at pH ${f.ph} and both were enumerated` : '. Paired alignment depth is insufficient for interaction discovery and the run was stopped at this layer for the declared claim'}. ${s(2)}.`,
    `Layer 3 placed the tool ${lig ? 'inside its validated regime but with pocket-level similarity of 71 to a pre-cutoff complex, so the result is reported as likely recall rather than generalisation' : 'inside its validated regime with pocket-level exposure below threshold'}. Exposure narrows the claim and does not by itself reduce confidence. ${s(3)}.`,
    lig
      ? `Layer 4 found the medoid pose physically valid under all PoseBusters tests, stable under restrained minimisation, and reproducing the hinge hydrogen bond and salt bridge seen in every crystal structure of the pocket. One buried amide N–H has no partner. ${s(4)}.`
      : `Layer 4 found the interface geometrically clean with a buried area of 1,240 Å², but Switch II adopts a state not observed experimentally for the GDP-bound target. ${s(4)}.`,
    lig
      ? `Layer 5 found ${f.seeds - 1} of ${f.seeds} seeds in one cluster, cross-family agreement of 1.1 Å between Boltz-2 and Gnina, and the redocking control reproduced the crystal pose. The pose threshold is borrowed from a benchmark and not yet recalibrated on this target. ${s(5)}.`
      : `Layer 5 found the ipTM of 0.71 within the range explained by partner length alone, and the decoy panel incomplete, so the comparative claim cannot be reported. ${s(5)}.`,
    `Verdict: ${verdict.statement}`,
  ];
}

/** addition: per-layer counts for the UI record. */
export function countResults(checks: UiCheck[]): Partial<Record<Result, number>> {
  const counts: Partial<Record<Result, number>> = {};
  for (const c of checks) counts[c.result] = (counts[c.result] || 0) + 1;
  return counts;
}

let counter = 0;
/** Records made so far in this session (prototype `counter`). */
export function mockRecordCount(): number {
  return counter;
}

export function makeRunRecord(form: MockForm, createdAt: number = Date.now()): UiRunRecord {
  const r = rng(createdAt % 100000);
  const task = (TASKS.find((t) => t.id === form.task) || TASKS.find((t) => t.id === 'ligand_pose')) as Task;
  const toolList0 = (form.tools || task.defaultTools).map((id) => TOOLS.find((t) => t.id === id)).filter((t): t is Tool => !!t);
  const cofoldTools = toolList0.filter((t) => t.family === 'co-folding');
  const dockTools = toolList0.filter((t) => t.family === 'docking');
  const primaryTool = cofoldTools[0] || toolList0[0] || TOOLS[0];
  const secondaryTool: Pick<Tool, 'name'> & { id?: string } = toolList0[1] || dockTools[0] || cofoldTools[1] || { name: 'Protenix', id: 'protenix' };
  const primary = primaryTool.name;
  const secondary = secondaryTool.name;
  const dockName = dockTools[0]?.name || null;
  const lig = ENTITIES.ligands.find((l) => l.smiles === form.ligand);
  const f: F = {
    ...form,
    task: task.kind === 'complex' ? 'interaction_discovery' : task.id === 'affinity_ranking' || task.id === 'virtual_screening' || task.id === 'series_scoring' ? 'affinity_ranking' : 'ligand_pose',
    realTask: task.id,
    claim: task.claim,
    createdAt,
    ccd: lig?.ccd,
    cid: lig?.cid,
    chembl: lig?.chembl,
    primary,
    secondary,
    dockName,
    primaryId: primaryTool.id,
    secondaryId: secondaryTool.id || null,
    dockId: dockTools[0]?.id || null,
  };
  const layers = layerChecks(f);
  const verdict = verdictFor(f, layers);
  counter += 1;
  const id = `run_${new Date(createdAt).toISOString().slice(0, 10).replace(/-/g, '')}_${hex(r, 6)}`;
  const toolList = toolList0;
  const summaries = layerSummary(f);
  const figures = layerFigures(f);
  const recordTools: RecordTool[] = toolList.map((t) => ({ ...t, container: `${t.id}_${t.version}.sif` }));
  const recordSources = sources(f, r);
  const recordLayers: RecordLayer[] = LAYERS.map((L, i) => ({
    i: L.i,
    key: L.key,
    name: L.name,
    question: L.question,
    checks: layers[i],
    summary: summaries[i],
    figures: figures[i],
    durationMs: Math.round(L.ms * (0.8 + r() * 0.4)),
    status: 'done',
    counts: countResults(layers[i]),
  }));
  const recordStats = stats(f, r);
  const execution: ExecutionLine[] = (() => {
    const isLig = task.id !== 'interaction_discovery';
    const ex: ExecutionLine[] = [];
    toolList.forEach((t) => {
      if (t.family === 'co-folding') ex.push({ tool: t.name, text: `${t.id} ${t.version} · ${form.seeds} seeds × 5 samples · recycling 3 · ${form.seeds * 5} structures retrieved (precomputed)`, plain: `${t.name}: ${form.seeds} seeds × 5 samples, ${form.seeds * 5} predicted structures retrieved.` });
      else if (isLig) ex.push({ tool: t.name, text: `${t.id} ${t.version} · autobox from ${form.reference} ligand +4 Å · exhaustiveness 16 · num_modes 9 · seeds ${form.seeds} · best score ${/gnina/i.test(t.name) ? 'CNN 0.79' : /diffdock/i.test(t.name) ? 'conf 0.71' : '−10.2 kcal/mol'}`, plain: `${t.name}: docked into a 24 × 22 × 26 Å box around the crystal ligand, 9 poses per seed.` });
      else ex.push({ tool: t.name, text: `${t.id} ${t.version} · ${form.seeds} seeds · 25 samples`, plain: `${t.name}: ${form.seeds} seeds.` });
    });
    if (isLig) ex.push({ tool: 'Redocking', text: `redock ${form.reference} crystal ligand · ${(dockName || 'vina').toLowerCase()} · RMSD 0.8 Å · control passed`, plain: `Redocking control: the crystal ligand was reproduced at 0.8 Å.` });
    return ex;
  })();
  const dockTool = dockTools[0];
  const dockParamValues: Record<string, string> = { autobox_add: '4', size: '24 × 22 × 26', exhaustiveness: '16', num_modes: '9' };
  const docking: DockingCard | null =
    dockName && task.kind === 'ligand'
      ? {
          tool: dockName,
          toolId: dockTool?.id,
          rows: [['box', '24 × 22 × 26 Å'], ['exhaustiveness', '16'], ['poses per seed', '9'], [/gnina/i.test(dockName) ? 'CNN pose score' : /diffdock/i.test(dockName) ? 'confidence' : 'score', /gnina/i.test(dockName) ? '0.79' : /diffdock/i.test(dockName) ? '0.71' : '−10.2 kcal/mol'], ['redocking RMSD', '0.8 Å'], [`vs ${primary} medoid`, '1.1 Å']],
          params: (dockTool?.dockingParams || []).filter((p) => p.key in dockParamValues).map((p) => ({ key: p.key, label: p.label, value: dockParamValues[p.key], unit: p.unit })),
        }
      : null;
  return {
    id,
    createdAt: new Date(createdAt).toISOString(),
    task: task.id,
    taskName: task.long,
    claim: task.claim,
    tools: recordTools,
    inputs: { target: form.target, partner: form.partner || null, ligand: form.ligand || null, reference: form.reference, ph: form.ph, seeds: form.seeds, samples: 5, assembly: task.id === 'interaction_discovery' ? 'A1:B1' : 'A1 + ligand' },
    sources: recordSources,
    layers: recordLayers,
    verdict,
    stats: recordStats,
    narrative: narrate(f, layers, verdict),
    controls: task.controls.map((c, i) => ({ name: c, status: verdict.outcome === 'refused' && i === 0 ? 'incomplete' : 'sound', note: verdict.outcome === 'refused' && i === 0 ? '6 of 12 decoy partners, paralogs absent' : i === 0 ? 'Reproduced under the same pipeline' : 'Run with identical settings' })),
    outputs: ['posebusters.csv', 'alphajudge.csv', 'plip_fingerprints.json', 'prolif_fingerprints.json', 'confidence_seed*.json', 'gnina.log', 'molprobity_summary.txt'].filter((o) => (task.id === 'interaction_discovery' ? !/posebusters|plip|gnina/.test(o) : !/molprobity/.test(o))),
    thresholds: [
      { name: 'Pocket exposure warn', value: '> 50 SuCOS×coverage', origin: 'PLINDER leakage analysis', level: 'published' },
      { name: 'Ligand strain warn', value: '> 16.1 kcal/mol', origin: 'StrainRelief paper', level: 'published' },
      { name: 'Minimisation drift warn', value: '> 2.0 Å', origin: 'Harness default', level: 'suspected' },
      { name: 'Boltz-2 pose confidence', value: 'ipTM ≥ 0.80', origin: 'Runs N’ Poses benchmark', level: 'borrowed, not recalibrated' },
      { name: 'Paired MSA depth stop', value: '< 32 sequences', origin: 'PPI harness calibration', level: 'reproduced' },
    ],
    execution,
    docking,
    status: 'done',
    record: { hardware: 'CSF3 · A100 40GB × 1 (predictions precomputed) · CPU checks live', scheduler: 'SLURM array 4471823', containers: toolList.map((t) => `${t.id}_${t.version}.sif`), acceleratedMode: 'stock', seeds: Array.from({ length: form.seeds }, (_, i) => 1000 + i * 17), notebook: `${id}.ipynb` },
    source: 'mock',
  };
}

export const SAMPLE_PROMPTS: string[] = [
  'Dock imatinib into the ABL1 kinase pocket with Boltz-2 and Gnina, 5 seeds at pH 7.4, compare against 1IEP',
  'Does KRAS interact with RAF1? Run Boltz-2 and Protenix with decoy partners',
  'Rank the imatinib congeneric series against ABL1 by Boltz-2 affinity, corroborate with Gnina, 8 seeds',
  'Screen the erlotinib library against EGFR with Vina and DiffDock-L, property-matched decoys',
  'Protein–protein dock KRAS with RAF1 using pyDock and HADDOCK, compare against 6VJJ',
];

export interface MockAgentStep {
  kind: 'thought' | 'tool' | 'result' | 'report' | 'conclusion';
  ms: number;
  text: string;
}
export interface MockAgentTask {
  id: string;
  goal: string;
  status: 'queued' | 'running' | 'done';
  steps: MockAgentStep[];
  outcome: { label: string; detail: string; runs: number; reports: number };
}

export const AGENT_TASKS: MockAgentTask[] = [
  { id: 'agent_01', goal: 'Decide whether the 12 Gnina poses for ABL1 · imatinib are valid', status: 'done', steps: [
    { kind: 'thought', ms: 1400, text: 'Pose validity is the ligand-pose task: PoseBusters, interaction chemistry, restrained minimisation and a redocking control. I will run all 12 poses through the harness and read the output-validity layer rather than the CNN score.' },
    { kind: 'tool', ms: 900, text: 'harness.submit · ligand_pose × 12 · Boltz-2 + Gnina · 5 seeds · reference 1IEP' },
    { kind: 'result', ms: 700, text: '12 jobs queued · 3 slots · redocking control shared' },
    { kind: 'tool', ms: 2600, text: 'harness.wait · jobs 1–3' },
    { kind: 'report', ms: 800, text: 'pose 01 · Narrowed · PoseBusters 20/20 · drift 0.6 Å · exposure 71' },
    { kind: 'report', ms: 600, text: 'pose 02 · Narrowed · PoseBusters 20/20 · 1 unsatisfied N–H' },
    { kind: 'report', ms: 600, text: 'pose 03 · Refused · minimum protein distance 1.6 Å · clash' },
    { kind: 'thought', ms: 1600, text: 'Pose 03 has a CNN score of 0.74, higher than pose 02, yet it clashes with Thr315. Confidence is not tracking geometry here, which is the failure mode the harness exists for. Continue with the remaining nine.' },
    { kind: 'tool', ms: 3200, text: 'harness.wait · jobs 4–12' },
    { kind: 'report', ms: 900, text: '9 jobs complete · 7 Narrowed · 2 Refused (poses 07, 11: stereocentre inverted; buried charge)' },
    { kind: 'tool', ms: 1100, text: 'harness.compare · poses vs crystal 1IEP · spyrmsd' },
    { kind: 'result', ms: 700, text: '9/12 within 2.0 Å of the crystal pose · all 3 refused poses > 4 Å' },
    { kind: 'conclusion', ms: 1200, text: '9 of 12 poses are physically valid and within stated uncertainty; 3 are refused at output validity. A confidence threshold of 0.7 would have accepted 11 of 12. Report and run records attached.' },
  ], outcome: { label: 'Completed', detail: '9 valid · 3 refused · confidence alone: 11 accepted', runs: 12, reports: 12 } },
  { id: 'agent_02', goal: 'Establish whether the KRAS · RAF1 interaction can be claimed from co-folding alone', status: 'running', steps: [
    { kind: 'thought', ms: 1500, text: 'Interaction discovery needs a complete decoy panel, a sticky control and a known positive before any comparative claim. First check what controls are available for KRAS in STRING and IntAct.' },
    { kind: 'tool', ms: 1000, text: 'sources.query · STRING v12.0 · IntAct · P01116 · experiments channel' },
    { kind: 'result', ms: 800, text: '41 experimentally supported partners · 6 length-matched non-cognate candidates in cache' },
    { kind: 'thought', ms: 1400, text: 'Six decoys is half the panel the task specification requires and no paralogs are included. I will submit the run anyway to read the interface metrics, expecting the controls check to stop the claim.' },
    { kind: 'tool', ms: 900, text: 'harness.submit · interaction_discovery · Boltz-2 + Protenix · 5 seeds · reference 6VJJ' },
    { kind: 'tool', ms: 4200, text: 'harness.wait · run_20261017_e1d265' },
    { kind: 'report', ms: 900, text: 'Refused · paired MSA depth 11 < 32 · ipTM 0.71 within length-confound range · decoys 6/12' },
    { kind: 'thought', ms: 1600, text: 'Two independent stops. The alignment problem is fixable by pairing against the full ColabFoldDB snapshot; the decoy panel needs six more proteins from the same proteome matched on length and composition.' },
    { kind: 'tool', ms: 1300, text: 'sources.query · UniProt proteome UP000005640 · length 160–220 · no STRING edge to P01116' },
    { kind: 'result', ms: 800, text: '6 candidates selected · 2 paralogs added (HRAS, NRAS) · panel 12/12' },
    { kind: 'tool', ms: 3800, text: 'harness.submit · interaction_discovery · paired MSA regenerated · decoys 12 · sticky control added' },
    { kind: 'report', ms: 900, text: 'Narrowed · paired depth 48 · ipTM 0.74 · above 11/12 decoys · sticky control below' },
    { kind: 'conclusion', ms: 1200, text: 'The complex is plausible relative to controls. The permitted claim stops there; the harness does not establish that the proteins bind.' },
  ], outcome: { label: 'Completed', detail: 'plausible relative to controls · 2 runs · panel rebuilt', runs: 2, reports: 2 } },
  { id: 'agent_03', goal: 'Rank the imatinib congeneric series against ABL1 and corroborate with docking', status: 'queued', steps: [
    { kind: 'thought', ms: 1400, text: 'Affinity ranking is permitted only as relative order within the series, with Boltz-2 affinity read on its own line and corroborated by Gnina scores and known actives from ChEMBL.' },
    { kind: 'tool', ms: 1000, text: 'sources.query · ChEMBL 35 · CHEMBL941 analogues · target CHEMBL1862 · IC50' },
    { kind: 'result', ms: 700, text: '12 series members · 9 with measured IC50 · 3 confirmed inactives' },
    { kind: 'tool', ms: 4000, text: 'harness.submit · affinity_ranking · Boltz-2 + Gnina · 8 seeds' },
    { kind: 'report', ms: 900, text: 'Narrowed · Kendall τ 0.82 across seeds · 2 members drift > 2 Å · ROC AUC 0.81 vs inactives' },
    { kind: 'conclusion', ms: 1200, text: 'Relative order is stable for 10 of 12 members; two are excluded for pose drift. No absolute affinity is reported.' },
  ], outcome: { label: 'Completed', detail: '10/12 ranked · τ 0.82 · AUC 0.81', runs: 1, reports: 1 } },
];

export interface PresetJob {
  name: string;
  form: MockForm;
  status: 'queued' | 'running' | 'done';
  layerIdx?: number;
}

export const PRESET_JOBS: PresetJob[] = [
  { name: 'ABL1 · imatinib pose', form: { task: 'ligand_pose', tools: ['boltz2', 'gnina'], target: 'P00519', ligand: ENTITIES.ligands[0].smiles, reference: '1IEP', ph: 7.4, seeds: 5 }, status: 'done' },
  { name: 'KRAS · RAF1 discovery', form: { task: 'interaction_discovery', tools: ['boltz2', 'protenix'], target: 'P01116', partner: 'P04049', reference: '6VJJ', ph: 7.4, seeds: 5 }, status: 'running', layerIdx: 3 },
  { name: 'ABL1 · series ranking', form: { task: 'affinity_ranking', tools: ['boltz2', 'gnina'], target: 'P00519', ligand: ENTITIES.ligands[0].smiles, reference: '1IEP', ph: 7.4, seeds: 8 }, status: 'queued' },
];

/** Settings → prototype form (fills the defaults the prototype `submit()` applied). */
export function formFromSettings(s: RunSettings): MockForm {
  return { task: s.task, tools: s.tools, target: s.target, ligand: s.ligand || '', partner: s.partner || '', reference: s.reference, ph: +s.ph || 7.4, seeds: +s.seeds || 5, name: s.name };
}

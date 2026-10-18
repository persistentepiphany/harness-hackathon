// Types shared by the viewer components. Kept apart from scene.ts so that no module outside the
// dynamically loaded Mol* chunk imports molstar code.

/** chain: by chain; confidence: pLDDT on the B-factor; flagged: residues named in findings; member: overlay colour. */
export type ColorMode = 'chain' | 'confidence' | 'flagged' | 'member';

export interface SceneResidue {
  num: number;
  chain?: string;
}

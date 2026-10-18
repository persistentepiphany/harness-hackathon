'use client';

// Request box: textarea, an Examples menu, Manual setup and Quick setup.

import { Button } from '@/components/ui';
import { Menu } from '@/components/ui/Menu';
import { parseToken, shortPrompt, TOKEN_MIME, type PromptToken } from '@/lib/selectors/run';

/** Sample requests shown under the box (prototype SAMPLE_PROMPTS, UI copy). */
export const SAMPLE_PROMPTS: string[] = [
  'Dock imatinib into the ABL1 kinase pocket with Boltz-2 and Gnina, 5 seeds at pH 7.4, compare against 1IEP',
  'Does KRAS interact with RAF1? Run Boltz-2 and Protenix with decoy partners',
  'Rank the imatinib congeneric series against ABL1 by Boltz-2 affinity, corroborate with Gnina, 8 seeds',
  'Screen the erlotinib library against EGFR with Vina and DiffDock-L, property-matched decoys',
  'Protein–protein dock KRAS with RAF1 using pyDock and HADDOCK, compare against 6VJJ',
];

export interface PromptBoxProps {
  text: string;
  onText: (text: string) => void;
  onUsePrompt: (prompt: string) => void;
  onQuick: () => void;
  onManual: () => void;
  quickBusy?: boolean;
  prompts?: string[];
  /** A tool, target or ligand chip dropped into the box, with the caret position. */
  onDropToken?: (token: PromptToken, caret: number | null) => void;
}

export function PromptBox({ text, onText, onUsePrompt, onQuick, onManual, quickBusy, prompts = SAMPLE_PROMPTS, onDropToken }: PromptBoxProps) {
  const empty = !text.trim();
  return (
    <div data-testid="prompt-box">
      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !empty) onQuick();
        }}
        onDragOver={(e) => {
          if (onDropToken && e.dataTransfer.types.includes(TOKEN_MIME)) e.preventDefault();
        }}
        onDrop={(e) => {
          const token = parseToken(e.dataTransfer.getData(TOKEN_MIME));
          if (!token || !onDropToken) return;
          e.preventDefault();
          onDropToken(token, e.currentTarget.selectionStart ?? null);
        }}
        placeholder="Dock imatinib into the ABL1 pocket with Boltz-2, 5 seeds, compare against 1IEP"
        aria-label="Describe the run"
        data-testid="prompt-input"
        rows={3}
        className="min-h-[92px] w-full resize-none rounded-card border border-line bg-surface px-4 py-3.5 text-[15px] leading-[1.5] text-ink placeholder:text-[#757575]"
      />
      <div className="mt-2.5 flex items-center justify-between gap-3">
        <Menu
          label="Examples"
          items={prompts.map((p) => ({ id: p, label: shortPrompt(p), title: p }))}
          selected={[]}
          onSelect={onUsePrompt}
          placeholder="Examples"
          className="w-[200px]"
          data-testid="sample-prompts"
        />
        <div className="flex items-center gap-1">
          <Button variant="ghost" onClick={onManual} data-testid="manual-setup">
            Manual setup
          </Button>
          <Button variant="secondary" onClick={onQuick} disabled={empty || quickBusy} data-testid="quick-setup">
            Quick setup
          </Button>
        </div>
      </div>
    </div>
  );
}

'use client';

// Prototype "New run" request box: textarea, sample prompts, Manual setup / Quick setup.

import { Button } from '@/components/ui';
import { shortPrompt } from '@/lib/selectors/run';

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
}

export function PromptBox({ text, onText, onUsePrompt, onQuick, onManual, quickBusy, prompts = SAMPLE_PROMPTS }: PromptBoxProps) {
  const empty = !text.trim();
  return (
    <div data-testid="prompt-box">
      <textarea
        value={text}
        onChange={(e) => onText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter' && (e.metaKey || e.ctrlKey) && !empty) onQuick();
        }}
        placeholder="Dock imatinib into the ABL1 pocket with Boltz-2, 5 seeds, compare against 1IEP"
        aria-label="Describe the run"
        data-testid="prompt-input"
        rows={3}
        className="min-h-[92px] w-full resize-none rounded-card border border-line bg-surface px-4 py-3.5 text-[15px] leading-[1.5] text-ink placeholder:text-[#757575]"
      />
      <div className="mt-3 flex flex-wrap gap-3.5">
        {prompts.map((p) => (
          <button
            key={p}
            type="button"
            title={p}
            onClick={() => onUsePrompt(p)}
            data-testid="sample-prompt"
            className="max-w-full overflow-hidden border-0 bg-transparent p-0 text-[12px] leading-[normal] text-ellipsis whitespace-nowrap text-muted hover:text-ink"
          >
            {shortPrompt(p)}
          </button>
        ))}
      </div>
      <div className="mt-3 flex items-center justify-end gap-2">
        <Button variant="secondary" onClick={onManual} data-testid="manual-setup">
          Manual setup
        </Button>
        <Button
          onClick={onQuick}
          disabled={empty || quickBusy}
          data-testid="quick-setup"
        >
          Quick setup
        </Button>
      </div>
    </div>
  );
}

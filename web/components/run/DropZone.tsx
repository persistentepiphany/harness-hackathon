'use client';

// Files: drop zone with a hidden file input. Files are POSTed to /ui/uploads; each chip shows the
// parse status the API returns (prototype `files`, without the simulated parsing). Uploads are
// stored only: the run settings carry no file references yet, so a note under the zone says so.

import clsx from 'clsx';
import { useRef, useState } from 'react';
import { fmtSha } from '@/lib/format';
import { RingDot, SectionHead } from './parts';

export const ACCEPTED_FILES = '.pdb,.cif,.mmcif,.fasta,.fa,.sdf,.mol,.mol2,.smi,.csv,.json';

export interface FileChipModel {
  /** Local id (name plus a counter), stable while the upload is in flight. */
  key: string;
  name: string;
  status: 'loading' | 'ok' | 'error';
  detail: string;
  sha256?: string | null;
}

export interface DropZoneProps {
  files: FileChipModel[];
  onFiles: (files: File[]) => void;
  onRemove: (key: string) => void;
}

export function DropZone({ files, onFiles, onRemove }: DropZoneProps) {
  const input = useRef<HTMLInputElement>(null);
  const [dragging, setDragging] = useState(false);
  return (
    <div>
      <SectionHead label="Files" hint="receptor, sequence, ligand or series · parsed on drop" />
      <div
        role="button"
        tabIndex={0}
        aria-label="Add files"
        data-testid="drop-zone"
        data-state={dragging ? 'dragging' : files.length ? 'files' : 'empty'}
        onDragOver={(e) => {
          e.preventDefault();
          if (!dragging) setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          if (e.dataTransfer?.files?.length) onFiles(Array.from(e.dataTransfer.files));
        }}
        onClick={(e) => {
          if ((e.target as HTMLElement).tagName === 'BUTTON') return;
          input.current?.click();
        }}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            input.current?.click();
          }
        }}
        className={clsx(
          'flex min-h-[72px] cursor-pointer items-center justify-center gap-2.5 rounded-card border border-dashed p-[18px] text-[12.5px] text-muted transition-all duration-150',
          dragging ? 'border-accent bg-accent-soft' : 'border-[#D7D7D2] bg-transparent',
        )}
      >
        <input
          ref={input}
          type="file"
          multiple
          accept={ACCEPTED_FILES}
          className="hidden"
          data-testid="file-input"
          onChange={(e) => {
            if (e.target.files?.length) onFiles(Array.from(e.target.files));
            e.target.value = '';
          }}
        />
        {files.length === 0 ? (
          <span>Drop PDB, mmCIF, FASTA, SDF or SMILES files</span>
        ) : (
          <div className="flex w-full flex-wrap gap-1.5">
            {files.map((f) => (
              <div
                key={f.key}
                data-testid="file-chip"
                data-state={f.status}
                title={f.sha256 ? `sha256 ${f.sha256}` : undefined}
                className="flex animate-fade-up items-center gap-2 rounded border border-line bg-surface px-[9px] py-[5px] text-[12px] text-ink"
              >
                <RingDot state={f.status} size={8} />
                <span className="font-mono">{f.name}</span>
                <span className={f.status === 'error' ? 'text-stop' : 'text-muted'}>{f.status === 'loading' ? 'parsing' : f.detail}</span>
                {f.sha256 && f.status === 'ok' ? <span className="font-mono text-[10.5px] text-faint">{fmtSha(f.sha256)}</span> : null}
                <button
                  type="button"
                  aria-label={`Remove ${f.name}`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onRemove(f.key);
                  }}
                  className="border-0 bg-transparent py-0 pr-0 pl-0.5 text-[13px] leading-none text-faint hover:text-ink"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
      {files.length > 0 && (
        <div className="mt-1.5 text-[11.5px] text-muted" data-testid="drop-zone-note">
          Stored, not used by the run: the run reads the target, ligand and reference named below.
        </div>
      )}
    </div>
  );
}

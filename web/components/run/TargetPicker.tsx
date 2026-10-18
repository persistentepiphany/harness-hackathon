"use client";

// Targets: catalog chips, "+ accession or name" input, detail card of the picked target.

import { Chip } from "@/components/ui";
import { DASH } from "@/lib/format";
import { targetRows, type TargetOption } from "@/lib/selectors/run";
import { DetailCard } from "./DetailCard";
import { AddInput, SectionHead } from "./parts";
import { targetToken } from "@/lib/selectors/run";
import { dragToken } from "./ToolPalette";

export interface TargetPickerProps {
  options: TargetOption[];
  selected: string;
  detail: TargetOption | null;
  /** UniProt release of the picked target, from the Sources lookups (row left out when absent). */
  release?: string | null;
  onSelect: (p: TargetOption) => void;
  addValue: string;
  onAddValue: (v: string) => void;
  onAdd: (v: string) => void;
}

export function TargetPicker({
  options,
  selected,
  detail,
  release,
  onSelect,
  addValue,
  onAddValue,
  onAdd,
}: TargetPickerProps) {
  return (
    <div data-testid="target-picker">
      <SectionHead
        label="Targets"
        hint="examples · any UniProt accession or name works"
      />
      <div className="flex flex-wrap items-center gap-1.5">
        {options.map((p) => (
          <Chip
            key={p.accession}
            selected={selected === p.accession}
            sub={p.accession}
            onClick={() => onSelect(p)}
            draggable
            onDragStart={(e) => dragToken(e, targetToken(p))}
            data-testid="target-chip"
            data-accession={p.accession}
            data-state={selected === p.accession ? "selected" : "idle"}
          >
            {p.label}
          </Chip>
        ))}
        <AddInput
          value={addValue}
          onChange={onAddValue}
          onSubmit={onAdd}
          placeholder="+ accession or name"
          width={170}
          data-testid="add-target"
        />
      </div>
      {detail && (
        <DetailCard
          data-testid="target-detail"
          title={detail.label}
          sub={`${detail.entry || DASH} · ${detail.accession}`}
          rows={targetRows(detail, release)}
        />
      )}
    </div>
  );
}

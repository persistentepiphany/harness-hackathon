// Tool-driven display helpers (docs/UI.md "Tools drive the display"). Screens never name a
// particular executor: labels, metric columns and families come from the tool register
// (GET /tools) and from the `tools` list of the record being shown.

import type { RecordTool, Tool, ToolFamily, ToolOutput, UiMetric, UiRunRecord } from './types';

/** A record tool resolved against the register; always has `outputs`. */
export type ResolvedTool = RecordTool & { outputs: ToolOutput[] };

type HasTools = Pick<UiRunRecord, 'tools'> | null | undefined;

function normalise(t: RecordTool | Tool, fromRegister?: Tool): ResolvedTool {
  const outputs = t.outputs && t.outputs.length ? t.outputs : (fromRegister?.outputs ?? []);
  return {
    ...(fromRegister ?? {}),
    ...t,
    family: familyOf(t) ?? familyOf(fromRegister) ?? undefined,
    outputs,
    dockingParams: t.dockingParams ?? fromRegister?.dockingParams,
  };
}

/**
 * The tool with `id` from the record (filled from `register` when the record entry lacks outputs).
 * A tool missing from both renders with its id as the name and no metric columns.
 */
export function toolById(record: HasTools, id: string, register?: Tool[] | null): ResolvedTool {
  const inRecord = record?.tools?.find((t) => t.id === id);
  const inRegister = register?.find((t) => t.id === id);
  if (inRecord) return normalise(inRecord, inRegister);
  if (inRegister) return normalise(inRegister);
  return { id, name: id, version: null, outputs: [] };
}

/** Tools of the record, in record order, resolved against the register. */
export function recordTools(record: HasTools, register?: Tool[] | null): ResolvedTool[] {
  return (record?.tools ?? []).map((t) => toolById(record, t.id, register));
}

/** `co-folding` | `docking`, accepting the register's `cofolding` spelling; null when unknown. */
export function familyOf(tool: { family?: string | null } | null | undefined): ToolFamily | null {
  const f = (tool?.family ?? '').toLowerCase().replace(/[^a-z]/g, '');
  if (f === 'cofolding') return 'co-folding';
  if (f === 'docking') return 'docking';
  return null;
}

/** The output definition for `key`, if the tool reports it. */
export function outputFor(tool: { outputs?: ToolOutput[] } | null | undefined, key: string): ToolOutput | undefined {
  return tool?.outputs?.find((o) => o.key === key);
}

/** Display label of an output key (falls back to the key itself). */
export function labelFor(tool: { outputs?: ToolOutput[] } | null | undefined, key: string): string {
  return outputFor(tool, key)?.label ?? key;
}

/** Unit of an output key, if any. */
export function unitFor(tool: { outputs?: ToolOutput[] } | null | undefined, key: string): string | undefined {
  return outputFor(tool, key)?.unit;
}

export interface MetricColumn {
  /** `${toolId}:${key}`, stable React key. */
  id: string;
  toolId: string;
  toolName: string;
  key: string;
  label: string;
  unit?: string;
  kind: ToolOutput['kind'];
  scope: ToolOutput['scope'];
  higherIsBetter?: boolean;
  range?: [number, number];
  note?: string;
  rankingOnly: boolean;
  /** The record's reported value for this output, when stats.metrics carries one. */
  metric?: UiMetric;
}

export interface MetricsForRecord {
  /** Structural and confidence outputs. */
  columns: MetricColumn[];
  /** `rankingOnly` outputs, shown below the accent rule. */
  rankingOnly: MetricColumn[];
}

/** Metric columns from the outputs of the record's tools, with ranking-only outputs separated. */
export function metricsFor(record: (HasTools & { stats?: UiRunRecord['stats'] }) | null | undefined, register?: Tool[] | null): MetricsForRecord {
  const metrics = record?.stats?.metrics ?? [];
  const columns: MetricColumn[] = [];
  const rankingOnly: MetricColumn[] = [];
  for (const tool of recordTools(record, register)) {
    for (const o of tool.outputs) {
      const col: MetricColumn = {
        id: `${tool.id}:${o.key}`,
        toolId: tool.id,
        toolName: tool.name,
        key: o.key,
        label: o.label,
        unit: o.unit,
        kind: o.kind,
        scope: o.scope,
        higherIsBetter: o.higherIsBetter,
        range: o.range,
        note: o.note,
        rankingOnly: !!o.rankingOnly,
        metric: metrics.find((m) => m.toolId === tool.id && m.key === o.key),
      };
      (col.rankingOnly ? rankingOnly : columns).push(col);
    }
  }
  return { columns, rankingOnly };
}

/** Group register tools by family for the executor chips (unknown family goes last). */
export function groupByFamily<T extends { family?: string | null }>(tools: T[]): { family: ToolFamily | null; tools: T[] }[] {
  const order: (ToolFamily | null)[] = ['co-folding', 'docking', null];
  return order
    .map((family) => ({ family, tools: tools.filter((t) => familyOf(t) === family) }))
    .filter((g) => g.tools.length > 0);
}

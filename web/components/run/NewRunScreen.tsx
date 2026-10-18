'use client';

// New run view (prototype `isNew` block): request box with Quick setup (interpreter steps streamed
// as decisions) or Manual setup (task, executors, inputs, run plan); target and ligand pickers;
// files; the Sources panel. Start run → POST /ui/runs → /reports/<jobId> (the report fills in live).

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ErrorState, Spinner } from '@/components/ui';
import { getHarnessApi, isAbortError, toApiError } from '@/lib/harness-api';
import { useAction, useCatalog, useEntities, useJobs, useTasks, useTools } from '@/lib/hooks';
import {
  applyStep,
  DEFAULT_SEEDS,
  defaultForm,
  fmtStep,
  formText,
  inputVisibility,
  ligandFromInput,
  requestSummary,
  selectTask,
  settingsFromForm,
  stepLabel,
  targetFromInput,
  taskGroups,
  taskHint,
  toggleTool,
  insertToken,
  type LigandOption,
  type RunForm,
  type TargetOption,
} from '@/lib/selectors/run';
import { groupEntities } from '@/lib/selectors/run';
import type { InterpretResult, StartRunResult, Step } from '@/lib/types';
import { DecisionStream, type DecisionRow } from './DecisionStream';
import { DropZone, type FileChipModel } from './DropZone';
import { InputsForm, type InputKey } from './InputsForm';
import { PromptBox } from './PromptBox';
import { SetupRow } from './SetupRow';
import { SourcesPanel } from './SourcesPanel';
import { TaskPicker } from './TaskPicker';

type Mode = 'quick' | 'manual' | null;

interface NlState {
  text: string;
  mode: Mode;
  rows: DecisionRow[];
  done: boolean;
}

/** Prototype quickSetup() timing: first row after 420 ms, one decision every 380 ms, check 300 ms later. */
const FIRST_MS = 420;
const STEP_MS = 380;
const CHECK_MS = 300;
const DONE_MS = 500;

export function NewRunScreen() {
  const router = useRouter();
  const catalog = useCatalog();
  const register = useTools();
  const tasks = useTasks();
  const jobs = useJobs();
  const interpret = useAction<InterpretResult>();
  const start = useAction<StartRunResult>();

  const base = useMemo(() => defaultForm(catalog.data, tasks.data), [catalog.data, tasks.data]);
  const [formState, setFormState] = useState<RunForm | null>(null);
  const form = formState ?? base;
  const update = (fn: (f: RunForm) => RunForm) => setFormState((prev) => fn(prev ?? base));

  const [nl, setNl] = useState<NlState>({ text: '', mode: null, rows: [], done: false });
  const [lookup, setLookup] = useState('');
  const [customTargets, setCustomTargets] = useState<TargetOption[]>([]);
  const [customLigands, setCustomLigands] = useState<LigandOption[]>([]);
  const [files, setFiles] = useState<FileChipModel[]>([]);

  const timers = useRef<ReturnType<typeof setTimeout>[]>([]);
  const uploads = useRef(new Set<AbortController>());
  const fileCounter = useRef(0);
  useEffect(() => {
    const t = timers.current;
    const u = uploads.current;
    return () => {
      t.forEach(clearTimeout);
      u.forEach((c) => c.abort());
    };
  }, []);
  const later = (ms: number, fn: () => void) => {
    timers.current.push(setTimeout(fn, ms));
  };
  const clearTimers = () => {
    timers.current.forEach(clearTimeout);
    timers.current = [];
  };

  const toolList = useMemo(() => {
    const reg = register.data ?? [];
    return reg;
  }, [register.data]);
  const task = tasks.data?.find((t) => t.id === form.task);
  const show = inputVisibility(task);
  const tg = useMemo(() => taskGroups(tasks.data), [tasks.data]);
  const entities = useEntities(lookup);
  const entityGroups = useMemo(() => groupEntities(entities.data), [entities.data]);

  const targetOptions: TargetOption[] = useMemo(() => {
    const list: TargetOption[] = [...(catalog.data?.proteins ?? [])];
    for (const c of customTargets) if (!list.some((p) => p.accession === c.accession)) list.push(c);
    return list;
  }, [catalog.data, customTargets]);
  const ligandOptions: LigandOption[] = useMemo(() => {
    const list: LigandOption[] = [...(catalog.data?.ligands ?? [])];
    for (const c of customLigands) if (!list.some((l) => l.smiles === c.smiles)) list.push(c);
    return list;
  }, [catalog.data, customLigands]);

  // ---------------------------------------------------------------- handlers

  const lookupForm = (f: RunForm) => setLookup(formText(f, catalog.data));

  const selectTarget = (p: TargetOption) => {
    const next = { ...form, target: p.accession, reference: p.pdb || form.reference };
    setFormState(next);
    lookupForm(next);
  };
  const selectLigand = (l: LigandOption) => {
    const next = { ...form, ligand: l.smiles };
    setFormState(next);
    lookupForm(next);
  };
  const addTarget = (v: string) => {
    const p = targetFromInput(v, catalog.data);
    if (!p) return;
    if (p.custom) setCustomTargets((list) => (list.some((x) => x.accession === p.accession) ? list : [...list, p]));
    selectTarget(p);
  };
  const addLigand = (v: string) => {
    const l = ligandFromInput(v, catalog.data);
    if (!l) return;
    if (l.custom) setCustomLigands((list) => (list.some((x) => x.smiles === l.smiles) ? list : [...list, l]));
    selectLigand(l);
  };

  const setInput = (key: InputKey, value: string) => {
    const next = { ...form, [key]: value };
    setFormState(next);
    if (key === 'target' || key === 'partner') lookupForm(next);
  };

  const quickSetup = async () => {
    const text = nl.text.trim();
    if (!text) return;
    clearTimers();
    setNl((n) => ({ ...n, mode: 'quick', rows: [{ label: 'Request', value: 'Reading', status: 'loading' }], done: false }));
    setLookup(text);
    const t0 = Date.now();
    const res = await interpret.run((api, signal) => api.interpret(text, { signal }));
    if (!res) return;
    const steps: Step[] = res.steps ?? [];
    let t = Math.max(0, FIRST_MS - (Date.now() - t0));
    later(t, () => setNl((n) => ({ ...n, rows: n.rows.map((r, k) => (k === 0 ? { ...r, value: requestSummary(text, steps), status: 'ok' } : r)) })));
    steps.forEach((s, i) => {
      t += STEP_MS;
      later(t, () => {
        update((f) => applyStep(f, s));
        setNl((n) => ({ ...n, rows: [...n.rows, { label: stepLabel(s.field), value: fmtStep(s, tasks.data, toolList), status: 'loading', field: s.field }] }));
      });
      later(t + CHECK_MS, () => setNl((n) => ({ ...n, rows: n.rows.map((r, k) => (k === i + 1 ? { ...r, status: 'ok', because: s.because } : r)) })));
    });
    later(t + DONE_MS, () => setNl((n) => ({ ...n, done: true })));
  };

  const manualSetup = () => {
    // a pending interpret request must not overwrite the form the user now edits by hand
    interpret.reset();
    clearTimers();
    setNl((n) => ({ ...n, mode: 'manual' }));
    lookupForm(form);
  };

  const submit = async () => {
    const settings = settingsFromForm(form, catalog.data, tasks.data, toolList);
    const r = await start.run((api, signal) => api.startRun(settings, { signal }));
    if (!r) return;
    jobs.reload();
    router.push(`/reports/${encodeURIComponent(r.jobId)}`);
  };

  const onFiles = (list: File[]) => {
    const batch: FileChipModel[] = list.map((f) => {
      fileCounter.current += 1;
      return { key: `${f.name}-${fileCounter.current}`, name: f.name, status: 'loading', detail: '' };
    });
    setFiles((prev) => [...prev, ...batch]);
    const c = new AbortController();
    uploads.current.add(c);
    const inBatch = (key: string) => batch.findIndex((b) => b.key === key);
    getHarnessApi()
      .uploadFiles(list, { signal: c.signal })
      .then(
        (res) =>
          setFiles((prev) =>
            prev.map((f) => {
              const i = inBatch(f.key);
              if (i < 0) return f;
              const r = res.files?.[i] ?? res.files?.find((x) => x.name === f.name);
              if (!r) return { ...f, status: 'error', detail: 'no result for this file' };
              return { ...f, status: r.status === 'error' ? 'error' : 'ok', detail: r.detail || r.kind || '', sha256: r.sha256 };
            }),
          ),
        (e: unknown) => {
          if (c.signal.aborted || isAbortError(e)) return;
          const err = toApiError(e);
          setFiles((prev) => prev.map((f) => (inBatch(f.key) >= 0 ? { ...f, status: 'error', detail: err.message } : f)));
        },
      )
      .finally(() => uploads.current.delete(c));
  };

  // ---------------------------------------------------------------- render

  const quickRows: DecisionRow[] =
    nl.mode === 'quick' && interpret.error && nl.rows.length <= 1
      ? [{ label: 'Request', value: `${interpret.error.message} (${interpret.error.code})`, status: 'error' }]
      : nl.rows;
  const side = entityGroups.length > 0 || entities.loading;
  const setupError = catalog.error ?? tasks.error ?? register.error;
  const loadingSetup = catalog.loading || tasks.loading;

  return (
    <main
      className={`mx-auto grid w-full animate-fade-up grid-cols-1 items-start gap-12 px-6 pt-11 pb-20 ${side ? 'max-w-[1080px] lg:grid-cols-[minmax(0,720px)_300px]' : 'max-w-[768px]'}`}
      data-testid="page-new-run"
      data-state={nl.mode ?? 'idle'}
    >
      <div className="flex min-w-0 flex-col gap-6">
        <h1 className="m-0 text-[18px] font-semibold tracking-[-0.01em]">New run</h1>
        <PromptBox
          text={nl.text}
          onText={(text) => {
            setNl((n) => ({ ...n, text }));
            setLookup(text);
          }}
          onUsePrompt={(p) => {
            interpret.reset();
            clearTimers();
            setNl({ text: p, mode: null, rows: [], done: false });
            setLookup(p);
          }}
          onQuick={quickSetup}
          onManual={manualSetup}
          quickBusy={interpret.loading}
          onDropToken={(token, caret) => {
            setNl((n) => {
              const next = insertToken(n.text, token.text, caret).text;
              setLookup(next);
              return { ...n, text: next };
            });
            if (token.kind === 'tool') update((f) => (f.tools.includes(token.id) ? f : { ...f, tools: [...f.tools, token.id] }));
            if (token.kind === 'target') {
              const p = targetOptions.find((o) => o.accession === token.id);
              if (p) selectTarget(p);
            }
            if (token.kind === 'ligand') {
              const l = ligandOptions.find((o) => o.smiles === token.id);
              if (l) selectLigand(l);
            }
          }}
        />

        {nl.mode === 'quick' && (
          <DecisionStream
            rows={quickRows}
            done={nl.done || (!!interpret.error && nl.rows.length <= 1)}
            onStart={submit}
            onAdjust={manualSetup}
            starting={start.loading}
            error={nl.mode === 'quick' ? start.error : null}
          />
        )}

        {setupError && (
          <ErrorState
            error={setupError}
            title="Setup data unavailable"
            onRetry={() => {
              catalog.reload();
              tasks.reload();
              register.reload();
            }}
          />
        )}
        {loadingSetup && !setupError && (
          <div className="flex items-center gap-2 text-[12.5px] text-muted" data-testid="setup-loading">
            <Spinner size={9} /> loading catalog and tasks
          </div>
        )}

        {catalog.data && register.data && (
          <SetupRow
            register={toolList}
            tools={form.tools}
            onToggleTool={(id) => update((f) => ({ ...f, tools: toggleTool(f.tools, id) }))}
            targets={targetOptions}
            target={form.target.trim().toUpperCase()}
            onTarget={selectTarget}
            onAddTarget={addTarget}
            ligands={show.ligand ? ligandOptions : null}
            ligand={form.ligand}
            onLigand={selectLigand}
            onAddLigand={addLigand}
            seeds={Number(form.seeds) || DEFAULT_SEEDS}
            onSeeds={(n) => update((f) => ({ ...f, seeds: String(n) }))}
            onStart={submit}
            starting={start.loading}
            error={nl.mode === 'quick' ? null : start.error}
            hideStart={nl.mode === 'quick'}
          />
        )}

        <DropZone files={files} onFiles={onFiles} onRemove={(key) => setFiles((prev) => prev.filter((f) => f.key !== key))} />

        {nl.mode === 'manual' && (
          <div className="flex animate-fade-up flex-col gap-[30px]" data-testid="manual-setup-panel">
            <TaskPicker
              cofolding={tg.cofolding}
              docking={tg.docking}
              selected={form.task}
              hint={taskHint(task)}
              onSelect={(t) => update((f) => selectTask(f, t, catalog.data))}
            />
            <InputsForm form={form} show={show} onChange={setInput} />
          </div>
        )}
      </div>

      {side && (
        <div className="sticky top-[68px] flex min-w-0 flex-col gap-7">
          <SourcesPanel groups={entityGroups} busy={entities.loading} error={entities.error} />
        </div>
      )}
    </main>
  );
}

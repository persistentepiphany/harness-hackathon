'use client';

// New run view (prototype `isNew` block): request box with Quick setup (interpreter steps streamed
// as decisions) or Manual setup (task, executors, inputs, run plan); target and ligand pickers;
// files; the Sources panel. Start run → POST /ui/runs → /jobs/<jobId>.

import { useRouter } from 'next/navigation';
import { useEffect, useMemo, useRef, useState } from 'react';
import { ErrorState, Spinner } from '@/components/ui';
import { ApiClient, toApiError, isAbortError } from '@/lib/api-client';
import { API_BASE } from '@/lib/config';
import { getHarnessApi } from '@/lib/harness-api';
import { useAction, useCatalog, useEntities, useJobs, useTasks, useTools } from '@/lib/hooks';
import {
  applyStep,
  defaultForm,
  executorGroups,
  findLigand,
  findProtein,
  fmtStep,
  formText,
  inputVisibility,
  ligandFromInput,
  planTools,
  requestSummary,
  selectTask,
  settingsFromForm,
  stepLabel,
  suggestName,
  targetFromInput,
  taskGroups,
  taskHint,
  toggleTool,
  type LigandOption,
  type RunForm,
  type TargetOption,
} from '@/lib/selectors/run';
import { groupEntities } from '@/lib/selectors/run';
import type { InterpretResult, StartRunResult, Step, Tool } from '@/lib/types';
import { DecisionStream, type DecisionRow } from './DecisionStream';
import { DropZone, type FileChipModel } from './DropZone';
import { ExecutorChips } from './ExecutorChips';
import { InputsForm, type InputKey } from './InputsForm';
import { LigandPicker } from './LigandPicker';
import { PromptBox } from './PromptBox';
import { RunPlan } from './RunPlan';
import { SourcesPanel } from './SourcesPanel';
import { TargetPicker } from './TargetPicker';
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
  const [add, setAdd] = useState({ target: '', ligand: '', tool: '' });
  const [customTargets, setCustomTargets] = useState<TargetOption[]>([]);
  const [customLigands, setCustomLigands] = useState<LigandOption[]>([]);
  const [customTools, setCustomTools] = useState<Tool[]>([]);
  const [detail, setDetail] = useState<{ target: string | null; ligand: string | null }>({ target: null, ligand: null });
  const [files, setFiles] = useState<FileChipModel[]>([]);
  const [addTool, setAddTool] = useState<{ busy: boolean; message: { code: string; message: string; status?: number } | null }>({ busy: false, message: null });

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

  const toolList = useMemo(() => [...(register.data ?? []), ...customTools], [register.data, customTools]);
  const task = tasks.data?.find((t) => t.id === form.task);
  const show = inputVisibility(task);
  const groups = useMemo(() => executorGroups(toolList, form.tools), [toolList, form.tools]);
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
  const targetDetail = detail.target && detail.target === form.target ? (targetOptions.find((p) => p.accession === detail.target) ?? null) : null;
  const ligandDetail = detail.ligand && detail.ligand === form.ligand ? (ligandOptions.find((l) => l.smiles === detail.ligand) ?? null) : null;

  // ---------------------------------------------------------------- handlers

  const lookupForm = (f: RunForm) => setLookup(formText(f, catalog.data));

  const selectTarget = (p: TargetOption) => {
    const next = { ...form, target: p.accession, reference: p.pdb || form.reference };
    setFormState(next);
    setDetail((d) => ({ ...d, target: p.accession }));
    lookupForm(next);
  };
  const selectLigand = (l: LigandOption) => {
    const next = { ...form, ligand: l.smiles };
    setFormState(next);
    setDetail((d) => ({ ...d, ligand: l.smiles }));
    lookupForm(next);
  };
  const addTarget = (v: string) => {
    const p = targetFromInput(v, catalog.data);
    if (!p) return;
    if (p.custom) setCustomTargets((list) => (list.some((x) => x.accession === p.accession) ? list : [...list, p]));
    selectTarget(p);
    setAdd((a) => ({ ...a, target: '' }));
  };
  const addLigand = (v: string) => {
    const l = ligandFromInput(v, catalog.data);
    if (!l) return;
    if (l.custom) setCustomLigands((list) => (list.some((x) => x.smiles === l.smiles) ? list : [...list, l]));
    selectLigand(l);
    setAdd((a) => ({ ...a, ligand: '' }));
  };

  const addExecutor = async (v: string) => {
    const [name, version] = v.split(':');
    const api = getHarnessApi();
    if (api.mode === 'mock') {
      // mock register: the prototype adds the entry to the session's tool list
      const id = name.toLowerCase().replace(/[^a-z0-9]/g, '');
      if (id && !toolList.some((t) => t.id === id)) {
        setCustomTools((list) => [
          ...list,
          { id, name, family: /dock/i.test(name) ? 'docking' : 'co-folding', role: 'Executor', version: version || 'latest', available: true, outputs: [], custom: true },
        ]);
      }
      if (id) update((f) => ({ ...f, tools: f.tools.includes(id) ? f.tools : [...f.tools, id] }));
      setAdd((a) => ({ ...a, tool: '' }));
      return;
    }
    // HarnessApi has no tool-registry call yet; POST /ui/tools directly through the proxy.
    setAddTool({ busy: true, message: null });
    try {
      await new ApiClient(API_BASE).post('/ui/tools', { name, version: version || null, image: v });
      setAddTool({ busy: false, message: null });
      setAdd((a) => ({ ...a, tool: '' }));
      register.reload();
    } catch (e) {
      if (isAbortError(e)) return;
      const err = toApiError(e);
      setAddTool({ busy: false, message: { code: err.code, message: err.message, status: err.status || undefined } });
    }
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
        if (s.field === 'target' && typeof s.value === 'string' && findProtein(catalog.data, s.value)) setDetail((d) => ({ ...d, target: String(s.value).toUpperCase() }));
        if (s.field === 'ligand' && typeof s.value === 'string') {
          const lig = findLigand(catalog.data, s.value);
          if (lig) setDetail((d) => ({ ...d, ligand: lig.smiles }));
        }
        setNl((n) => ({ ...n, rows: [...n.rows, { label: stepLabel(s.field), value: fmtStep(s, tasks.data, toolList), status: 'loading', field: s.field }] }));
      });
      later(t + CHECK_MS, () => setNl((n) => ({ ...n, rows: n.rows.map((r, k) => (k === i + 1 ? { ...r, status: 'ok', because: s.because } : r)) })));
    });
    later(t + DONE_MS, () => setNl((n) => ({ ...n, done: true })));
  };

  const manualSetup = () => {
    clearTimers();
    setNl((n) => ({ ...n, mode: 'manual' }));
    lookupForm(form);
  };

  const submit = async () => {
    const settings = settingsFromForm(form, catalog.data, tasks.data);
    const r = await start.run((api, signal) => api.startRun(settings, { signal }));
    if (!r) return;
    jobs.reload();
    router.push(`/jobs/${encodeURIComponent(r.jobId)}`);
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
  const setupError = catalog.error ?? tasks.error ?? register.error;
  const loadingSetup = catalog.loading || tasks.loading;

  return (
    <main
      className="mx-auto grid w-full max-w-[1160px] animate-fade-up grid-cols-[minmax(0,1fr)_300px] items-start gap-12 px-6 pt-11 pb-20"
      data-testid="page-new-run"
      data-state={nl.mode ?? 'idle'}
    >
      <div className="flex min-w-0 flex-col gap-[30px]">
        <h1 className="m-0 text-[18px] font-semibold tracking-[-0.01em]">New run</h1>
        <PromptBox
          text={nl.text}
          onText={(text) => {
            setNl((n) => ({ ...n, text }));
            setLookup(text);
          }}
          onUsePrompt={(p) => {
            clearTimers();
            setNl({ text: p, mode: null, rows: [], done: false });
            setLookup(p);
          }}
          onQuick={quickSetup}
          onManual={manualSetup}
          quickBusy={interpret.loading}
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

        {catalog.data && (
          <TargetPicker
            options={targetOptions}
            selected={form.target.trim().toUpperCase()}
            detail={targetDetail}
            onSelect={selectTarget}
            addValue={add.target}
            onAddValue={(v) => setAdd((a) => ({ ...a, target: v }))}
            onAdd={addTarget}
          />
        )}

        {catalog.data && show.ligand && (
          <LigandPicker
            options={ligandOptions}
            selected={form.ligand}
            detail={ligandDetail}
            onSelect={selectLigand}
            addValue={add.ligand}
            onAddValue={(v) => setAdd((a) => ({ ...a, ligand: v }))}
            onAdd={addLigand}
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
            {register.loading && !register.data ? (
              <div className="flex items-center gap-2 text-[12.5px] text-muted">
                <Spinner size={9} /> loading executors
              </div>
            ) : (
              <ExecutorChips
                groups={groups}
                onToggle={(id) => update((f) => ({ ...f, tools: toggleTool(f.tools, id) }))}
                addValue={add.tool}
                onAddValue={(v) => {
                  setAdd((a) => ({ ...a, tool: v }));
                  if (addTool.message) setAddTool({ busy: false, message: null });
                }}
                onAdd={addExecutor}
                addBusy={addTool.busy}
                addMessage={addTool.message}
              />
            )}
            <InputsForm form={form} show={show} onChange={setInput} />
          </div>
        )}
      </div>

      <div className="sticky top-[68px] flex min-w-0 flex-col gap-7">
        <SourcesPanel groups={entityGroups} busy={entities.loading} error={entities.error} />
        {nl.mode === 'manual' && (
          <RunPlan
            name={form.name}
            suggestion={suggestName(form, catalog.data, tasks.data)}
            onName={(v) => update((f) => ({ ...f, name: v }))}
            claim={task?.claim ?? ''}
            tools={planTools(form.tools, toolList)}
            controls={task?.controls.join(', ') ?? ''}
            onStart={submit}
            starting={start.loading}
            error={start.error}
          />
        )}
      </div>
    </main>
  );
}

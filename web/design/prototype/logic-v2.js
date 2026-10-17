class Component extends DCLogic {
  state = {
    view: 'new', data: null, jobs: [], runJobId: null, reportJobId: null, reportLayer: 4, vizTab: 'pae', structSel: 'medoid', logMode: 'plain',
    nl: { text: '', mode: null, stream: [], done: false }, entities: [], files: [], dragging: false, detail: { target: null, ligand: null, loading: {} },
    form: { task: 'ligand_pose', tools: ['boltz2', 'gnina'], target: 'P00519', ligand: 'Cc1ccc(NC(=O)c2ccc(CN3CCN(C)CC3)cc2)cc1Nc1nccc(-c2cccnc2)n1', partner: '', reference: '1IEP', ph: 7.4, seeds: 5, name: '' },
    viewerBusy: false, viewerStatus: '', tick: 0, agent: { tasks: [], sel: null }, add: { target: '', ligand: '', tool: '' },
  };
  P = { pass: '#3B8A58', warn: '#C28A1A', stop: '#C4513B', reported: '#8B8B85', accent: '#B07E2C' };
  T = { pass: '#E4F1E8', warn: '#FAF0D9', stop: '#F9E5E0', reported: '#EFEFEB' };
  INTER = { 'H-bond': '#3B8A58', 'Salt bridge': '#B07E2C', 'Hydrophobic': '#8B8B85', 'π stacking': '#5B7FA6' };
  KIND = { crystal: '#1A1A18', medoid: '#B07E2C', seed: '#C9A86A', docking: '#5B7FA6', model: '#8B6FB5' };
  _grid = {};

  async componentDidMount() {
    const data = await import('./data/runs.js');
    const now = Date.now();
    const jobs = data.PRESET_JOBS.map((p, i) => this.makeJob(data, p.form, p.name, now - (3 - i) * 95000, p.status, p.layerIdx));
    const agentTasks = data.AGENT_TASKS.map(t => { const total = t.steps.reduce((a, s) => a + s.ms, 0); const elapsed = t.status === 'done' ? total : t.status === 'running' ? Math.round(total * 0.45) : 0; return { ...t, total, elapsedMs: elapsed, startedAt: now - elapsed }; });
    this.setState({ data, jobs, runJobId: jobs[1].id, reportJobId: jobs[0].id, agent: { tasks: agentTasks, sel: agentTasks[1].id } });
    this._last = performance.now();
    this._timer = setInterval(() => this.tick(), 110);
  }
  componentWillUnmount() { clearInterval(this._timer); try { this._viewer?.dispose?.(); } catch (e) {} Object.values(this._grid).forEach(g => { try { g.viewer?.dispose?.(); } catch (e) {} }); }
  componentDidUpdate() { if (this._logEl) this._logEl.scrollTop = this._logEl.scrollHeight; this.ensureViewer(); if (this._paeEl) this.drawPae(this._paeEl); }

  // ---------- jobs ----------
  makeJob(data, form, name, createdAt, status = 'queued', layerIdx = 0) {
    const record = data.makeRunRecord(form, createdAt);
    const job = { id: record.id, name: name || this.suggestName(form, data), form, record, status, layerIdx: status === 'done' ? 6 : layerIdx, progress: 0, elapsedMs: 0, log: [], emitted: {}, createdAt };
    if (status !== 'queued') { this.startLines(job); const n = status === 'done' ? 6 : layerIdx; for (let i = 0; i < n; i++) { job.elapsedMs += record.layers[i].durationMs; this.emitLayer(job, i, 1); } }
    return job;
  }
  startLines(job) { job.log.push({ layer: 0, kind: 'exec', t: '0.0s', text: `slot acquired · ${job.record.tools.map(t => t.container).join(' ')}`, plain: `Started. ${job.record.tools.map(t => t.name).join(' and ')} outputs are precomputed; checks run live.` }); job.record.execution.forEach(e => job.log.push({ layer: 0, kind: 'exec', t: '0.0s', text: e.text, plain: e.plain })); }
  suggestName(form, data = this.state.data) { if (!data) return ''; const t = data.TASKS.find(x => x.id === form.task); const p = data.CATALOG.proteins.find(p => p.accession === form.target); return `${p ? p.label : form.target} · ${t ? t.name.toLowerCase() : 'run'}`; }
  linesFor(job, i) {
    const rec = job.record; const chk = (c) => ({ layer: i, kind: 'check', result: c.result, text: `${c.id} [${c.tool}] → ${c.result} · ${c.evidence} · ${c.ms} ms`, plain: `${c.name}: ${c.evidence}` });
    if (i === 0) return rec.sources.map(s => ({ layer: 0, kind: s.cached ? 'cache' : 'fetch', result: null, text: `${s.cached ? 'cache' : 'GET'} ${s.source} ${s.accession} · ${s.release} · sha256 ${s.sha256.slice(0, 10)}… · ${s.ms} ms`, plain: `${s.cached ? 'Used cached' : 'Fetched'} ${s.supplies.toLowerCase()} from ${s.source} (${s.accession}, ${s.release}) in ${s.ms} ms` })).concat(rec.layers[0].checks.map(chk));
    return rec.layers[i].checks.map(chk);
  }
  emitLayer(job, i, frac) {
    const lines = this.linesFor(job, i); const want = Math.min(lines.length, Math.floor(frac * lines.length + 1e-6)); const have = job.emitted[i] || 0;
    for (let k = have; k < want; k++) job.log.push({ ...lines[k], t: (job.elapsedMs / 1000).toFixed(1) + 's' });
    job.emitted[i] = Math.max(have, want);
    if (frac >= 1 && !job.log.some(l => l.kind === 'layer' && l.layer === i)) {
      const L = job.record.layers[i]; const chk = L.checks; const stops = chk.filter(c => c.result === 'stop').length; const warns = chk.filter(c => c.result === 'warn').length;
      job.log.push({ layer: i, kind: 'layer', result: stops ? 'stop' : warns ? 'warn' : 'pass', t: (job.elapsedMs / 1000).toFixed(1) + 's', text: `── ${L.name.toLowerCase()} · ${chk.length} checks · ${stops ? stops + ' stop' : warns ? warns + ' warn' : 'clean'} · ${L.durationMs} ms`, plain: `${L.name} finished in ${(L.durationMs / 1000).toFixed(1)} s: ${chk.length} checks, ${stops ? stops + ' stopped the claim' : warns ? warns + ' warned' : 'all clean'}.` });
    }
  }
  tick() {
    const now = performance.now(); const dt = Math.min(400, now - this._last); this._last = now;
    const speed = this.props.simSpeed ?? 1; const maxC = this.props.maxConcurrent ?? 3; let changed = false;
    const jobs = this.state.jobs.map(j => ({ ...j })); let running = jobs.filter(j => j.status === 'running').length;
    for (const j of jobs) {
      if (j.status === 'queued' && running < maxC) { j.status = 'running'; j.log = [...j.log]; this.startLines(j); running++; changed = true; }
      if (j.status !== 'running') continue;
      changed = true; j.elapsedMs += dt * speed; j.progress += (dt * speed) / j.record.layers[j.layerIdx].durationMs; j.log = [...j.log]; j.emitted = { ...j.emitted };
      if (j.progress >= 1) { this.emitLayer(j, j.layerIdx, 1); j.layerIdx += 1; j.progress = 0; if (j.layerIdx >= 6) { j.status = 'done'; const o = j.record.verdict.outcome; j.log.push({ layer: 5, kind: 'layer', result: o === 'refused' ? 'stop' : o === 'narrowed' ? 'warn' : 'pass', t: (j.elapsedMs / 1000).toFixed(1) + 's', text: `verdict · ${o} · ${(j.elapsedMs / 1000).toFixed(1)} s total · report generated`, plain: `Verdict: ${o} after ${(j.elapsedMs / 1000).toFixed(1)} s. The report is ready.` }); } }
      else this.emitLayer(j, j.layerIdx, j.progress);
    }
    let agent = this.state.agent;
    if (agent.tasks.length) {
      const tasks = agent.tasks.map(t => ({ ...t })); let anyRunning = tasks.some(t => t.status === 'running'); let ch = false;
      for (const t of tasks) {
        if (t.status === 'queued' && !anyRunning) { t.status = 'running'; anyRunning = true; ch = true; }
        if (t.status !== 'running') continue;
        t.elapsedMs += dt * speed; ch = true;
        if (t.elapsedMs >= t.total) { t.elapsedMs = t.total; t.status = 'done'; anyRunning = false; }
      }
      if (ch) { agent = { ...agent, tasks }; changed = true; }
    }
    if (changed) this.setState({ jobs, agent, tick: this.state.tick + 1 });
  }

  // ---------- entities ----------
  scheduleLookup(text) {
    clearTimeout(this._lookupT);
    this._lookupT = setTimeout(() => {
      const d = this.state.data; if (!d) return;
      const found = d.lookupEntities(text); const have = new Set(this.state.entities.map(e => e.key));
      const fresh = found.filter(e => !have.has(e.key)).map(e => ({ ...e, status: 'loading' })); const keep = this.state.entities.filter(e => found.some(f => f.key === e.key));
      if (!fresh.length && keep.length === this.state.entities.length) return;
      this.setState({ entities: [...keep, ...fresh] });
      fresh.forEach(e => setTimeout(() => this.setState({ entities: this.state.entities.map(x => x.key === e.key ? { ...x, status: 'ok' } : x) }), e.ms + Math.random() * 300));
    }, 350);
  }
  formText(f) { const d = this.state.data; const lig = d?.CATALOG.ligands.find(l => l.smiles === f.ligand); return `${f.target} ${f.partner} ${lig ? lig.names[0] : ''} ${this.state.nl.text}`; }
  selectTarget(p) { const form = { ...this.state.form, target: p.accession, reference: p.pdb }; this.setState({ form, detail: { ...this.state.detail, target: p.accession, loading: { ...this.state.detail.loading, target: true } } }); setTimeout(() => this.setState({ detail: { ...this.state.detail, loading: { ...this.state.detail.loading, target: false } } }), 650); this.scheduleLookup(this.formText(form)); }
  selectLigand(l) { const form = { ...this.state.form, ligand: l.smiles }; this.setState({ form, detail: { ...this.state.detail, ligand: l.ccd, loading: { ...this.state.detail.loading, ligand: true } } }); setTimeout(() => this.setState({ detail: { ...this.state.detail, loading: { ...this.state.detail.loading, ligand: false } } }), 550); this.scheduleLookup(this.formText(form)); }

  // ---------- setup ----------
  quickSetup = () => {
    const { data, nl } = this.state; if (!data || !nl.text.trim()) return;
    const res = data.interpretRun(nl.text);
    const labels = { task: 'Task', tools: 'Executors', target: 'Target', partner: 'Partner', ligand: 'Ligand', seeds: 'Seeds', ph: 'pH', reference: 'Reference', claim: 'Claim' };
    const fmt = (s) => s.field === 'tools' ? s.value.map(id => data.TOOLS.find(t => t.id === id)?.name).join(' · ') : s.field === 'task' ? data.TASKS.find(t => t.id === s.value)?.long : s.field === 'ligand' && s.value.length > 40 ? s.value.slice(0, 38) + '…' : String(s.value);
    this.setState({ nl: { ...nl, mode: 'quick', stream: [{ label: 'Request', value: 'Reading', status: 'loading' }], done: false } }); this.scheduleLookup(nl.text);
    const prot = data.CATALOG.proteins.find(p => p.accession === res.target); const lig = data.CATALOG.ligands.find(l => l.smiles === res.ligand);
    let t = 420; setTimeout(() => this.patchStream(0, { value: `${nl.text.trim().split(/\s+/).length} tokens · ${res.steps.length} decisions`, status: 'ok' }), t);
    res.steps.forEach((s, i) => { t += 380;
      setTimeout(() => { const f = { ...this.state.form }; if (s.field !== 'claim') f[s.field] = s.value; this.setState({ form: f, detail: { ...this.state.detail, target: prot ? prot.accession : this.state.detail.target, ligand: lig ? lig.ccd : this.state.detail.ligand }, nl: { ...this.state.nl, stream: [...this.state.nl.stream, { label: labels[s.field] || s.field, value: fmt(s), status: 'loading' }] } }); }, t);
      setTimeout(() => this.patchStream(i + 1, { status: 'ok', value: `${fmt(s)}  —  ${s.because}` }), t + 300); });
    setTimeout(() => this.setState({ nl: { ...this.state.nl, done: true } }), t + 500);
  };
  patchStream(i, patch) { this.setState({ nl: { ...this.state.nl, stream: this.state.nl.stream.map((r, k) => k === i ? { ...r, ...patch } : r) } }); }
  manualSetup = () => { this.setState({ nl: { ...this.state.nl, mode: 'manual' } }); this.scheduleLookup(this.formText(this.state.form)); };
  submit = () => {
    const { data, form } = this.state; if (!data) return;
    const job = this.makeJob(data, { ...form, seeds: +form.seeds || 5, ph: +form.ph || 7.4 }, form.name || this.suggestName(form), Date.now(), 'queued');
    this.setState({ jobs: [job, ...this.state.jobs], runJobId: job.id, view: 'run', form: { ...form, name: '' }, nl: { text: '', mode: null, stream: [], done: false }, entities: [], files: [], detail: { target: null, ligand: null, loading: {} } });
  };
  setForm(k) { return (e) => { const form = { ...this.state.form, [k]: e.target.value }; this.setState({ form }); if (k === 'target' || k === 'partner') this.scheduleLookup(this.formText(form)); }; }

  // ---------- add your own ----------
  setAdd(k) { return (e) => this.setState({ add: { ...this.state.add, [k]: e.target.value } }); }
  addKey(k) { return (e) => { if (e.key !== 'Enter') return; const v = (this.state.add[k] || '').trim(); if (!v) return; const d = this.state.data; if (!d) return;
    if (k === 'target') { const acc = /^[A-Z][0-9][A-Z0-9]{3}[0-9]$/i.test(v) ? v.toUpperCase() : null; const p = d.CATALOG.proteins.find(p => p.names.some(n => v.toLowerCase().includes(n))) || { names: [v.toLowerCase()], accession: acc || v, entry: 'pending', label: v, organism: '—', length: 0, pdb: this.state.form.reference, resolution: '—', holo: 0, afPlddt: 0, sites: 0, domains: '—', disorder: '—', cofactors: '—', custom: true }; if (!d.CATALOG.proteins.includes(p)) d.CATALOG.proteins.push(p); this.selectTarget(p); }
    if (k === 'ligand') { const l = d.CATALOG.ligands.find(l => l.names.some(n => v.toLowerCase().includes(n)) || l.ccd === v.toUpperCase()) || { names: [v.length > 12 ? 'custom ligand' : v], smiles: v, ccd: v.length <= 3 ? v.toUpperCase() : 'NEW', cid: '—', chembl: '—', formula: 'pending', mw: '—', inchikey: 'computed on submit', activities: 0, stereo: 0, pka: 'enumerated at run', custom: true }; if (!d.CATALOG.ligands.includes(l)) d.CATALOG.ligands.push(l); this.selectLigand(l); }
    if (k === 'tool') { const [name, version] = v.split(':'); const id = name.toLowerCase().replace(/[^a-z0-9]/g, ''); if (!d.TOOLS.find(t => t.id === id)) d.TOOLS.push({ id, name, family: /vina|gnina|dock|haddock/i.test(name) ? 'docking' : 'co-folding', role: 'Executor', version: version || 'latest', available: true, custom: true }); this.setState({ form: { ...this.state.form, tools: [...this.state.form.tools, id] } }); }
    this.setState({ add: { ...this.state.add, [k]: '' } }); }; }

  // ---------- files ----------
  addFiles(list) {
    const kinds = { pdb: 'receptor', cif: 'receptor', mmcif: 'receptor', fasta: 'sequence', fa: 'sequence', sdf: 'ligand', mol: 'ligand', mol2: 'ligand', smi: 'ligand', csv: 'series', json: 'manifest' };
    const files = Array.from(list).map(f => { const ext = f.name.split('.').pop().toLowerCase(); return { name: f.name, size: f.size, kind: kinds[ext] || 'file', status: 'loading' }; });
    this.setState({ files: [...this.state.files, ...files] });
    files.forEach(f => setTimeout(() => this.setState({ files: this.state.files.map(x => x.name === f.name ? { ...x, status: 'ok', parsed: this.parsedLabel(x) } : x) }), 500 + Math.random() * 600));
  }
  parsedLabel(f) { return { receptor: 'receptor · chains A,B · 0 gaps', sequence: 'sequence · 1 chain', ligand: 'ligand · sanitised · InChIKey ok', series: 'series · 12 members', manifest: 'manifest' }[f.kind] || `${(f.size / 1024).toFixed(0)} kB`; }
  onDrop = (e) => { e.preventDefault(); this.setState({ dragging: false }); if (e.dataTransfer?.files?.length) this.addFiles(e.dataTransfer.files); };
  onDragOver = (e) => { e.preventDefault(); if (!this.state.dragging) this.setState({ dragging: true }); };
  onDragLeave = () => this.setState({ dragging: false });
  fileInputRef = (el) => { this._fileInput = el; };
  browseFiles = (e) => { if (e.target.tagName === 'BUTTON') return; this._fileInput?.click(); };
  onFiles = (e) => { if (e.target.files?.length) this.addFiles(e.target.files); e.target.value = ''; };

  // ---------- viewers ----------
  viewerOpts = { layoutIsExpanded: false, layoutShowControls: false, layoutShowSequence: false, layoutShowLog: false, layoutShowLeftPanel: false, viewportShowExpand: false, viewportShowSelectionMode: false, viewportShowAnimation: false, viewportShowSettings: false, viewportShowTrajectoryControls: false, pdbProvider: 'rcsb', emdbProvider: 'rcsb' };
  async loadInto(v, rec, sel) { try { await v.plugin.clear(); if (sel === 'crystal' || String(sel).startsWith('gnina')) await v.loadPdb(rec.inputs.reference); else if (sel === 'overlay') { await v.loadPdb(rec.inputs.reference); await v.loadAlphaFoldDb(rec.inputs.target); } else await v.loadAlphaFoldDb(rec.inputs.target); } catch (e) {} }
  viewerRef = (el) => { if (!el) { try { this._viewer?.dispose?.(); } catch (e) {} this._viewer = null; this._viewerKey = null; this._viewerEl = null; return; } this._viewerEl = el; this.ensureViewer(); };
  ensureViewer() {
    const rec = this.reportRecord(); if (!rec || !this._viewerEl || !window.molstar || this._creating) return;
    const sel = this.state.structSel; const key = `${rec.id}|${sel}`; if (this._viewerKey === key) return; this._viewerKey = key;
    const load = async (v) => { this.setState({ viewerBusy: true, viewerStatus: sel === 'crystal' ? `RCSB ${rec.inputs.reference}` : sel === 'overlay' ? 'overlay · crystal + predicted' : `AlphaFold DB ${rec.inputs.target} · pLDDT colouring` }); await this.loadInto(v, rec, sel); if (this._viewerKey === key) this.setState({ viewerBusy: false }); };
    if (!this._viewer) { this._creating = true; window.molstar.Viewer.create(this._viewerEl, this.viewerOpts).then(v => { this._creating = false; this._viewer = v; try { v.plugin.canvas3d?.setProps({ renderer: { backgroundColor: 0xFFFFFF } }); } catch (e) {} load(v); }).catch(() => { this._creating = false; }); }
    else load(this._viewer);
  }
  gridRef(id, sel) {
    if (!this._grid[id]) this._grid[id] = {};
    const g = this._grid[id];
    if (!g.ref) g.ref = (el) => { if (!el) { try { g.viewer?.dispose?.(); } catch (e) {} g.viewer = null; g.key = null; g.creating = false; return; } g.el = el; this.ensureGrid(id); };
    g.sel = sel; return g.ref;
  }
  ensureGrid(id) {
    const g = this._grid[id]; const rec = this.reportRecord(); if (!g || !g.el || !rec || !window.molstar || g.creating) return;
    const key = `${rec.id}|${g.sel}`; if (g.key === key) return; g.key = key;
    if (!g.viewer) { g.creating = true; window.molstar.Viewer.create(g.el, this.viewerOpts).then(v => { g.creating = false; g.viewer = v; try { v.plugin.canvas3d?.setProps({ renderer: { backgroundColor: 0xFFFFFF } }); } catch (e) {} this.loadInto(v, rec, g.sel); }).catch(() => { g.creating = false; }); }
    else this.loadInto(g.viewer, rec, g.sel);
  }
  paeRef = (el) => { this._paeEl = el; if (el) this.drawPae(el); };
  drawPae(el) {
    const rec = this.reportRecord(); if (!rec || el._pdb === rec.id) return; el._pdb = rec.id;
    const ctx = el.getContext('2d'); const n = 48; const cell = el.width / n; const disc = rec.task === 'interaction_discovery'; const split = disc ? 28 : 38;
    let s = 7; const r = () => { s = (s * 1664525 + 1013904223) >>> 0; return s / 4294967296; }; const mix = (a, b, t) => a.map((x, k) => Math.round(x + (b[k] - x) * t));
    for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) { const same = (i < split) === (j < split); const d = Math.abs(i - j); let pae = same ? Math.min(30, 1 + d * 0.25 + r() * 2.5) : (disc ? 9 + r() * 12 : 2.5 + r() * 2); const t = Math.min(1, pae / 30); const c = t < 0.5 ? mix([47, 107, 79], [185, 215, 195], t * 2) : mix([185, 215, 195], [246, 246, 243], (t - 0.5) * 2); ctx.fillStyle = `rgb(${c.join(',')})`; ctx.fillRect(i * cell, j * cell, cell + 0.5, cell + 0.5); }
    ctx.strokeStyle = '#B07E2C'; ctx.lineWidth = 1.5; ctx.strokeRect(split * cell + 0.75, 0.75, (n - split) * cell - 1.5, split * cell - 1.5);
  }
  logRef = (el) => { this._logEl = el; if (el) el.scrollTop = el.scrollHeight; };
  reportRecord() { const j = this.state.jobs.find(x => x.id === this.state.reportJobId && x.status === 'done') || this.state.jobs.find(x => x.status === 'done'); return j ? j.record : null; }
  go(view) { return () => this.setState({ view }); }
  download(name, text, type = 'application/json') { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([text], { type })); a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(a.href), 2000); }
  downloadRecord = () => { const r = this.reportRecord(); if (r) this.download(`${r.id}.json`, JSON.stringify(r, null, 2)); };
  downloadNotebook = () => {
    const r = this.reportRecord(); if (!r) return; const cell = (src) => ({ cell_type: 'code', metadata: {}, outputs: [], execution_count: null, source: src });
    const nb = { nbformat: 4, nbformat_minor: 5, metadata: { kernelspec: { name: 'python3', display_name: 'Python 3' }, papermill: { parameters: { run_record: `${r.id}.json` } } }, cells: [{ cell_type: 'markdown', metadata: {}, source: `# ${r.id}\nReruns every query and check from the run record.` }, cell(`import json\nrecord = json.load(open('${r.id}.json'))`), cell(`for s in record['sources']:\n    assert fetch(s['source'], s['accession'], s['release']).sha256 == s['sha256'], s`), ...r.layers.slice(1).map(l => cell(`# ${l.name}\nfor c in record['layers'][${l.i}]['checks']:\n    assert run_check(c['id'], record['inputs']).result == c['result'], c['id']`))] };
    this.download(r.record.notebook, JSON.stringify(nb, null, 2));
  };
  stats(arr) { const a = arr.filter(x => typeof x === 'number' && !isNaN(x)).sort((x, y) => x - y); if (!a.length) return null; const mean = a.reduce((s, x) => s + x, 0) / a.length; const med = a.length % 2 ? a[(a.length - 1) / 2] : (a[a.length / 2 - 1] + a[a.length / 2]) / 2; const sd = Math.sqrt(a.reduce((s, x) => s + (x - mean) ** 2, 0) / Math.max(1, a.length - 1)); return { median: med, mean, sd, min: a[0], max: a[a.length - 1] }; }

  renderVals() {
    const { view, data, jobs, form, nl, entities, files, detail } = this.state; const P = this.P, T = this.T;
    const running = jobs.filter(j => j.status === 'running').length, queued = jobs.filter(j => j.status === 'queued').length, done = jobs.filter(j => j.status === 'done').length;
    const tabs = [['new', 'New run'], ['jobs', 'Jobs', running + queued], ['report', 'Reports', done], ['ensemble', 'Ensemble'], ['agent', 'Agent', this.state.agent.tasks.filter(t => t.status === 'running').length], ['docs', 'Documents', done]].map(([id, label, badge]) => ({ label, go: this.go(id), underline: view === id || (id === 'jobs' && view === 'run') ? '#1A1A18' : 'transparent', color: view === id || (id === 'jobs' && view === 'run') ? '#1A1A18' : '#8B8B85', hasBadge: !!badge, badge }));
    const spinner = (st) => st === 'loading' ? { ring: '#E6E6E1', ringTop: P.accent, anim: 'spin .8s linear infinite', fill: 'transparent' } : { ring: P.pass, ringTop: P.pass, anim: 'none', fill: P.pass };
    const vals = {
      tabs, isNew: view === 'new', isJobs: view === 'jobs', isRun: view === 'run', isReport: view === 'report', isEnsemble: view === 'ensemble', isAgent: view === 'agent', isDocs: view === 'docs', goNew: this.go('new'), goJobs: this.go('jobs'), goReport: this.go('report'), goEnsemble: this.go('ensemble'),
      clusterStatus: running ? `${running} running · ${queued} queued` : queued ? `${queued} queued` : 'idle', clusterDotColor: running ? P.accent : '#B9B9B3', clusterDotAnim: running ? 'pulse 1.4s infinite' : 'none',
      useMolstar: (this.props.viewerMode ?? 'molstar') === 'molstar', usePlaceholder: (this.props.viewerMode ?? 'molstar') !== 'molstar', viewerBusy: this.state.viewerBusy, viewerStatus: this.state.viewerStatus,
    };
    if (!data) return vals;
    const task = data.TASKS.find(t => t.id === form.task) || data.TASKS[0]; const isDisc = task.kind === 'complex';
    // ----- new run -----
    const chip = (t) => { const on = form.tools.includes(t.id); return { ...t, disabled: !t.available, note: t.note || '', cursor: t.available ? 'pointer' : 'not-allowed', opacity: t.available ? 1 : 0.45, toggle: () => this.setState({ form: { ...form, tools: on ? form.tools.filter(x => x !== t.id) : [...form.tools, t.id] } }) }; };
    const groups = []; entities.forEach(e => { let g = groups.find(x => x.title === e.title); if (!g) { g = { title: e.title, color: e.kind === 'protein' ? P.accent : '#5B7FA6', items: [] }; groups.push(g); } g.items.push({ ...e, ...spinner(e.status), loading: e.status === 'loading', ok: e.status === 'ok', rows: e.rows.map(([k, v]) => ({ k, v })) }); });
    const tp = data.CATALOG.proteins.find(p => p.accession === (detail.target || form.target)); const tl = data.CATALOG.ligands.find(l => l.ccd === detail.ligand || l.smiles === form.ligand);
    const selTarget = detail.target || form.target; const selLig = tl?.ccd;
    Object.assign(vals, {
      nlText: nl.text, onNlText: e => { this.setState({ nl: { ...nl, text: e.target.value } }); this.scheduleLookup(e.target.value); }, quickSetup: this.quickSetup, manualSetup: this.manualSetup, quickDisabled: !nl.text.trim(), quickOpacity: nl.text.trim() ? 1 : 0.4,
      samplePrompts: data.SAMPLE_PROMPTS.map(p => ({ short: p.split(/[,.?]/)[0] + (p.includes('?') ? '?' : ''), use: () => { this.setState({ nl: { text: p, mode: null, stream: [], done: false } }); this.scheduleLookup(p); } })),
      streamVisible: nl.mode === 'quick', streamDone: nl.done, stream: nl.stream.map(s => ({ ...s, ...spinner(s.status), color: s.status === 'loading' ? '#8B8B85' : '#1A1A18' })), manualVisible: nl.mode === 'manual',
      targetChips: data.CATALOG.proteins.map(p => { const on = selTarget === p.accession; return { label: p.label, accession: p.accession, select: () => this.selectTarget(p), bg: on ? '#1A1A18' : 'transparent', color: on ? '#fff' : '#1A1A18', border: on ? '#1A1A18' : '#E6E6E1', sub: on ? '#B9B9B3' : '#8B8B85' }; }),
      hasTargetDetail: !!(detail.target && tp), td: tp ? { label: tp.label, entry: tp.entry, accession: tp.accession, loading: !!detail.loading.target, ready: !detail.loading.target, rows: [['Length', `${tp.length.toLocaleString()} aa`], ['Organism', tp.organism], ['Domains', tp.domains], ['Cofactors', tp.cofactors], ['Holo entries', String(tp.holo)], ['Reference', `${tp.pdb} · ${tp.resolution}`], ['AF pLDDT', String(tp.afPlddt)], ['Disorder', tp.disorder], ['Binding sites', `${tp.sites} · PDBe-KB`], ['Release', 'UniProt 2026_04']].map(([k, v]) => ({ k, v })) } : {},
      ligandChips: data.CATALOG.ligands.map(l => { const on = selLig === l.ccd; return { label: l.names[0], ccd: l.ccd, select: () => this.selectLigand(l), bg: on ? '#1A1A18' : 'transparent', color: on ? '#fff' : '#1A1A18', border: on ? '#1A1A18' : '#E6E6E1', sub: on ? '#B9B9B3' : '#8B8B85' }; }),
      hasLigandDetail: !!(detail.ligand && tl), ld: tl ? { label: tl.names[0], formula: tl.formula, mw: tl.mw, loading: !!detail.loading.ligand, ready: !detail.loading.ligand, rows: [['CCD', tl.ccd], ['PubChem', `CID ${tl.cid}`], ['ChEMBL', `${tl.chembl} · ${tl.activities.toLocaleString()} activities`], ['InChIKey', tl.inchikey], ['Stereocentres', String(tl.stereo)], ['pKa', tl.pka], ['SMILES', tl.smiles]].map(([k, v]) => ({ k, v })) } : {},
      taskOptionsCofold: data.TASKS.filter(t => t.group === 'co-folding').map(t => ({ name: t.name, select: () => this.setState({ form: { ...form, task: t.id, tools: t.defaultTools, partner: t.kind === 'complex' ? (form.partner || 'P04049') : form.partner } }), bg: form.task === t.id ? '#1A1A18' : 'transparent', color: form.task === t.id ? '#fff' : '#1A1A18', border: form.task === t.id ? '#1A1A18' : '#E6E6E1' })),
      taskOptionsDock: data.TASKS.filter(t => t.group === 'docking').map(t => ({ name: t.name, select: () => this.setState({ form: { ...form, task: t.id, tools: t.defaultTools, partner: t.kind === 'complex' ? (form.partner || 'P04049') : form.partner } }), bg: form.task === t.id ? '#1A1A18' : 'transparent', color: form.task === t.id ? '#fff' : '#55554F', border: form.task === t.id ? '#1A1A18' : '#E6E6E1' })),
      taskClaimHint: `permitted claim: ${task.claim}`,
      cofoldChips: data.TOOLS.filter(t => t.family === 'co-folding').map(chip).map(c => ({ ...c, bg: form.tools.includes(c.id) ? '#F6EEDC' : 'transparent', border: form.tools.includes(c.id) ? P.accent : '#E6E6E1' })),
      dockChips: data.TOOLS.filter(t => t.family === 'docking').map(chip).map(c => ({ ...c, bg: form.tools.includes(c.id) ? '#F1F1ED' : 'transparent', border: form.tools.includes(c.id) ? '#55554F' : '#E6E6E1' })),
      form, showPartner: isDisc, showLigand: !isDisc,
      onTarget: this.setForm('target'), onPartner: this.setForm('partner'), onReference: this.setForm('reference'), onSeeds: this.setForm('seeds'), onPh: this.setForm('ph'), onLigand: this.setForm('ligand'), onName: this.setForm('name'),
      onDrop: this.onDrop, onDragOver: this.onDragOver, onDragLeave: this.onDragLeave, browseFiles: this.browseFiles, onFiles: this.onFiles, fileInputRef: this.fileInputRef, dropBorder: this.state.dragging ? P.accent : '#D7D7D2', dropBg: this.state.dragging ? '#FBF7EE' : 'transparent',
      noFiles: files.length === 0, hasFiles: files.length > 0, files: files.map(f => ({ ...f, ...spinner(f.status), parsed: f.status === 'ok' ? f.parsed : 'parsing', remove: (e) => { e.stopPropagation(); this.setState({ files: this.state.files.filter(x => x.name !== f.name) }); } })),
      entitiesBusy: entities.some(e => e.status === 'loading'), noEntities: entities.length === 0, entityGroups: groups,
      addTarget: this.state.add.target, onAddTarget: this.setAdd('target'), onAddTargetKey: this.addKey('target'), addLigand: this.state.add.ligand, onAddLigand: this.setAdd('ligand'), onAddLigandKey: this.addKey('ligand'), addTool: this.state.add.tool, onAddTool: this.setAdd('tool'), onAddToolKey: this.addKey('tool'),
      nameSuggestion: this.suggestName(form), planClaim: task.claim, planTools: form.tools.map(id => data.TOOLS.find(t => t.id === id)?.name).filter(Boolean).join(' · ') || 'none', planControls: task.controls.join(', '), submit: this.submit,
    });
    // ----- jobs + run -----
    const worst = (checks) => checks.some(c => c.result === 'stop') ? 'stop' : checks.some(c => c.result === 'warn') ? 'warn' : 'pass';
    const vmeta = (o) => o === 'refused' ? { label: 'Refused', color: P.stop } : o === 'narrowed' ? { label: 'Narrowed', color: '#8E6420' } : { label: 'Supported', color: P.pass };
    const openReport = (j) => (e) => { e && e.stopPropagation && e.stopPropagation(); this.setState({ reportJobId: j.id, view: 'report', structSel: 'medoid', reportLayer: j.record.verdict.outcome === 'refused' ? j.record.layers.findIndex(l => l.checks.some(c => c.result === 'stop')) : 4 }); };
    vals.jobsSummary = `${running} running · ${queued} queued · ${done} done`;
    vals.jobCards = jobs.map((j, idx) => { const vm = vmeta(j.record.verdict.outcome); const L = j.record.layers[Math.min(j.layerIdx, 5)]; const allC = j.record.layers.flatMap(l => l.checks); const doneC = j.log.filter(l => l.kind === 'check').length;
      return { ...j, num: String(jobs.length - idx).padStart(2, '0'), taskName: data.TASKS.find(t => t.id === j.form.task)?.name, taskLong: data.TASKS.find(t => t.id === j.form.task)?.long, tools: j.record.tools.map(t => t.name).join(' + '), toolsLong: j.record.tools.map(t => `${t.name} ${t.version}`).join(', '), inputs: `${j.form.target}${j.form.partner ? ' + ' + j.form.partner : ''} · ${j.form.reference} · ${j.form.seeds} seeds · pH ${j.form.ph}`, claim: j.record.claim, checksLine: j.status === 'done' ? `${allC.length} checks · ${allC.filter(c => c.result === 'warn').length} warn · ${allC.filter(c => c.result === 'stop').length} stop` : `${doneC} of ${allC.length} checks`, seeds: j.form.seeds, open: () => this.setState({ runJobId: j.id, view: 'run' }), done: j.status === 'done', notDone: j.status !== 'done', verdictLabel: vm.label, verdictColor: vm.color, elapsed: `${(j.elapsedMs / 1000).toFixed(1)} s`,
        dot: j.status === 'running' ? P.accent : '#B9B9B3', dotAnim: j.status === 'running' ? 'pulse 1.2s infinite' : 'none', statusLabel: j.status === 'running' ? `${L.name.toLowerCase()} · ${(j.elapsedMs / 1000).toFixed(1)}s` : 'queued',
        segs: j.record.layers.map((l, i) => { const dl = i < j.layerIdx; const cur = i === j.layerIdx && j.status === 'running'; const w = worst(l.checks); const wn = l.checks.filter(c => c.result === 'warn').length, st = l.checks.filter(c => c.result === 'stop').length; return { i, name: l.name, pct: dl ? 100 : cur ? Math.round(j.progress * 100) : 0, color: dl ? (w === 'pass' ? '#1A1A18' : w === 'warn' ? P.warn : P.stop) : P.accent, labelColor: dl || cur ? '#55554F' : '#C9C9C3', counts: dl ? (st ? `${st} stop` : wn ? `${wn} warn` : `${l.checks.length}`) : '' }; }) }; });
    const sel = jobs.find(j => j.id === this.state.runJobId) || jobs[0];
    const lines = sel ? sel.log : []; const term = this.state.logMode === 'terminal';
    const LOGC = term ? { pass: '#6FBF8A', warn: '#E3B45A', stop: '#E8826E', fetch: '#C9C9C3', cache: '#8B8B85', exec: '#C9C9C3' } : { pass: P.pass, warn: P.warn, stop: P.stop, fetch: '#1A1A18', cache: '#55554F', exec: '#1A1A18' };
    if (sel) { const vm = vmeta(sel.record.verdict.outcome); const curL = sel.record.layers[Math.min(sel.layerIdx, 5)]; const allC = sel.record.layers.flatMap(l => l.checks);
      vals.rj = { name: sel.name, id: sel.id, taskName: data.TASKS.find(t => t.id === sel.form.task)?.long, tools: sel.record.tools.map(t => `${t.name} ${t.version}`).join(' · '), seeds: sel.form.seeds, elapsed: `${(sel.elapsedMs / 1000).toFixed(1)} s`, done: sel.status === 'done', openReport: openReport(sel),
        statusLabel: sel.status === 'done' ? `complete · ${allC.length} checks` : sel.status === 'running' ? `${curL.name.toLowerCase()} · ${Math.round(sel.progress * 100)}%` : 'queued', statusColor: sel.status === 'done' ? P.pass : '#55554F', dot: sel.status === 'running' ? P.accent : sel.status === 'done' ? P.pass : '#B9B9B3', dotAnim: sel.status === 'running' ? 'pulse 1.2s infinite' : 'none',
        currentStep: sel.status === 'running' ? (lines.length ? lines[lines.length - 1].text.slice(0, 60) : 'starting') : sel.status === 'done' ? `finished · ${(sel.elapsedMs / 1000).toFixed(1)} s` : 'queued',
        layers: sel.record.layers.map((l, i) => { const dl = i < sel.layerIdx; const cur = i === sel.layerIdx && sel.status === 'running'; const p = l.checks.filter(c => c.result === 'pass').length, w = l.checks.filter(c => c.result === 'warn').length, s = l.checks.filter(c => c.result === 'stop').length; return { name: l.name, bar: dl ? P[worst(l.checks)] : cur ? P.accent : '#E6E6E1', color: dl || cur ? '#1A1A18' : '#B9B9B3', value: dl ? `${(l.durationMs / 1000).toFixed(1)} s` : cur ? `${Math.round(sel.progress * 100)}%` : '—', valueColor: dl ? '#1A1A18' : cur ? P.accent : '#B9B9B3', counts: dl ? `${p}${w ? ` · ${w}w` : ''}${s ? ` · ${s}s` : ''}` : cur ? l.summary[0] : '' }; }),
        execution: sel.record.execution.map(e => ({ ...e, ...spinner(sel.status === 'queued' ? 'loading' : 'ok') })), inputsLine1: `${sel.form.target}${sel.form.partner ? ' + ' + sel.form.partner : ''} · ${sel.form.reference} · pH ${sel.form.ph}`, inputsLine2: `${sel.form.seeds} seeds × 5 samples · ${sel.record.inputs.assembly}`,
        verdictLabel: vm.label, verdictColor: vm.color, claim: sel.record.claim, verdictCounts: `${allC.filter(c => c.result === 'pass').length} pass · ${allC.filter(c => c.result === 'warn').length} warn · ${allC.filter(c => c.result === 'stop').length} stop` };
    } else vals.rj = {};
    Object.assign(vals, {
      logEmpty: lines.length === 0, logRef: this.logRef,
      logBg: term ? '#1A1A18' : '#fff', logFg: term ? '#E8E8E3' : '#1A1A18', logBorder: term ? '#1A1A18' : '#E6E6E1', logLine: term ? 'rgba(255,255,255,.08)' : '#EFEFEB', logMuted: term ? '#6B6B66' : '#B9B9B3', logToggleBg: term ? 'rgba(255,255,255,.08)' : '#F1F1ED', logFont: term ? "'Geist Mono',ui-monospace,monospace" : 'Geist,system-ui,sans-serif', logSize: term ? '11px' : '12.5px', logPad: term ? '1px' : '4px',
      termBg: term ? '#fff' : 'transparent', termFg: term ? '#1A1A18' : '#8B8B85', plainBg: term ? 'transparent' : '#fff', plainFg: term ? '#8B8B85' : '#1A1A18', setTerminal: () => this.setState({ logMode: 'terminal' }), setPlain: () => this.setState({ logMode: 'plain' }),
      logLines: lines.map(l => ({ t: l.t, text: term ? l.text : l.plain, weight: l.kind === 'layer' ? 500 : 400, dotColor: l.result ? LOGC[l.result] : l.kind === 'fetch' ? P.accent : l.kind === 'exec' ? '#5B7FA6' : term ? '#55554F' : '#D7D7D2', color: term ? (l.kind === 'layer' ? '#fff' : l.result ? LOGC[l.result] : LOGC[l.kind]) : (l.kind === 'layer' ? '#1A1A18' : l.result === 'stop' ? P.stop : l.result === 'warn' ? '#8E6420' : '#55554F') })),
      evPass: lines.filter(l => l.kind === 'check' && l.result === 'pass').length, evWarn: lines.filter(l => l.kind === 'check' && l.result === 'warn').length, evStop: lines.filter(l => l.kind === 'check' && l.result === 'stop').length, evFetched: lines.filter(l => l.kind === 'fetch' || l.kind === 'cache').length, evChecks: lines.filter(l => l.kind === 'check').length,
    });
    // ----- agent -----
    { const A = this.state.agent; const KC = { thought: '#8B8B85', tool: '#5B7FA6', result: '#55554F', report: P.accent, conclusion: '#1A1A18' };
      const prog = (t) => { let acc = 0, n = 0; for (const s of t.steps) { acc += s.ms; if (t.elapsedMs >= acc) n++; else break; } return n; };
      const selT = A.tasks.find(t => t.id === A.sel) || A.tasks[0];
      vals.ag = { summary: `${A.tasks.filter(t => t.status === 'running').length} running · ${A.tasks.filter(t => t.status === 'done').length} completed`,
        tasks: A.tasks.map(t => { const n = prog(t); const on = selT && selT.id === t.id; return { goal: t.goal, select: () => this.setState({ agent: { ...A, sel: t.id } }), bg: on ? '#fff' : 'transparent', border: on ? '#1A1A18' : '#E6E6E1', statusLabel: t.status === 'done' ? t.outcome.label.toLowerCase() : t.status, statusColor: t.status === 'done' ? P.pass : '#55554F', dot: t.status === 'running' ? P.accent : t.status === 'done' ? P.pass : '#B9B9B3', dotAnim: t.status === 'running' ? 'pulse 1.2s infinite' : 'none', pct: Math.round(Math.min(1, t.elapsedMs / t.total) * 100), barColor: t.status === 'done' ? P.pass : P.accent, stepLabel: `${n}/${t.steps.length} steps · ${t.outcome.runs} runs`, elapsed: `${(t.elapsedMs / 1000).toFixed(0)} s` }; }),
        sel: selT ? (() => { const n = prog(selT); let acc = 0; const steps = selT.steps.slice(0, n).map((s, i) => { const t0 = acc; acc += s.ms; return { kind: s.kind, text: s.text, t: `${(t0 / 1000).toFixed(1)}s`, kindColor: KC[s.kind], color: s.kind === 'thought' ? '#55554F' : '#1A1A18', size: s.kind === 'thought' ? '13px' : s.kind === 'conclusion' ? '14px' : '12px', font: s.kind === 'tool' || s.kind === 'result' || s.kind === 'report' ? "'Geist Mono',ui-monospace,monospace" : 'Geist,system-ui,sans-serif', weight: s.kind === 'conclusion' ? 500 : 400, radius: s.kind === 'tool' || s.kind === 'result' ? '2px' : '50%', fill: s.kind === 'thought' ? 'transparent' : KC[s.kind], stroke: KC[s.kind], strokeTop: KC[s.kind], anim: 'none' }; });
          const next = selT.steps[n]; const allC = selT.steps.slice(0, n);
          return { goal: selT.goal, id: selT.id, stepsDone: n, stepsTotal: selT.steps.length, toolCalls: allC.filter(s => s.kind === 'tool').length, reports: allC.filter(s => s.kind === 'report').length, elapsed: `${(selT.elapsedMs / 1000).toFixed(1)} s`, done: selT.status === 'done', outcomeLabel: selT.outcome.label, outcomeDetail: selT.outcome.detail, steps, thinking: selT.status === 'running' && !!next, nextKind: next ? ({ thought: 'thinking', tool: 'calling ' + next.text.split(' ')[0], result: 'waiting for result', report: 'reading report', conclusion: 'writing conclusion' }[next.kind]) : '' }; })() : {} };
    }
    // ----- report / ensemble / docs -----
    const doneJobs = jobs.filter(j => j.status === 'done'); const rj = doneJobs.find(j => j.id === this.state.reportJobId) || doneJobs[0];
    const pick = (j) => () => this.setState({ reportJobId: j.id, structSel: 'medoid' });
    vals.reportPicker = doneJobs.map(j => ({ name: j.name, pick: pick(j), underline: rj && rj.id === j.id ? '#1A1A18' : 'transparent', color: rj && rj.id === j.id ? '#1A1A18' : '#8B8B85' }));
    vals.docList = doneJobs.map(j => { const vm = vmeta(j.record.verdict.outcome); const on = rj && rj.id === j.id; return { name: j.name, pick: pick(j), bar: on ? '#1A1A18' : '#E6E6E1', weight: on ? 600 : 500, verdictLabel: vm.label, verdictColor: vm.color, date: new Date(j.record.createdAt).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) }; });
    vals.noReport = !rj; vals.hasReport = !!rj; vals.openDoc = () => this.setState({ view: 'docs' }); vals.downloadRecord = this.downloadRecord; vals.downloadNotebook = this.downloadNotebook; vals.printDoc = () => window.print(); vals.viewerRef = this.viewerRef; vals.paeRef = this.paeRef;
    if (!rj) { vals.rp = {}; vals.en = {}; return vals; }
    if (rj.id !== this.state.reportJobId) setTimeout(() => this.setState({ reportJobId: rj.id }), 0);
    const r = rj.record; const vm = vmeta(r.verdict.outcome); const li = Math.min(5, Math.max(0, this.state.reportLayer)); const L = r.layers[li]; const lig = r.task !== 'interaction_discovery'; const S = r.stats;
    const resColor = (res) => res === 'reported' ? P.reported : P[res];
    const ss = this.state.structSel; const selEnt = S.ensemble.find(e => e.id === ss || (ss === 'medoid' && e.kind === 'medoid'));
    const seedPts = S.seeds.map(s => ({ cx: 40 + Math.min(8, s.rmsdToMedoid) / 8 * 310, cy: 128 - (s.confidence - 0.5) / 0.5 * 108, ty: 128 - (s.confidence - 0.5) / 0.5 * 108 + 15, fill: s.rmsdToMedoid < 2 ? P.pass : P.warn, label: `s${s.seed}` }));
    const calib = (key) => S.calibration.map(p => `${40 + (p.x - 0.5) / 0.5 * 270},${130 - p[key] * 115}`).join(' ');
    const flagged = r.layers.flatMap(l => l.checks.filter(c => c.result === 'warn' || c.result === 'stop')).map(c => ({ ...c, color: P[c.result] }));
    const allChecks = r.layers.flatMap(l => l.checks);
    const inter = S.interactions.map((it, i, arr) => { const a = -Math.PI / 2 + i * 2 * Math.PI / arr.length; const R = 112; return { ...it, x: +(180 + R * Math.cos(a)).toFixed(1), y: +(150 + R * Math.sin(a)).toFixed(1), lx: +(180 + (R + 30) * Math.cos(a)).toFixed(1), ly: +(150 + (R + 30) * Math.sin(a) + 3).toFixed(1), stroke: this.INTER[it.type] || '#8B8B85', dash: it.type === 'Hydrophobic' ? '3 3' : it.type === 'H-bond' ? '5 3' : '0', knownLabel: it.known ? 'known' : 'new' }; });
    vals.vizTabs = [['pae', 'PAE'], ['inter', 'Interactions'], ['seeds', 'Seeds'], ['agree', 'Agreement'], ['calib', S.roc ? 'Calibration · ROC' : 'Calibration']].map(([id, label]) => ({ label, select: () => this.setState({ vizTab: id }), underline: this.state.vizTab === id ? '#1A1A18' : 'transparent', color: this.state.vizTab === id ? '#1A1A18' : '#8B8B85' }));
    ['pae', 'inter', 'seeds', 'agree', 'calib'].forEach(id => vals['viz' + id[0].toUpperCase() + id.slice(1)] = this.state.vizTab === id);
    const physHead = lig ? ['drift Å', 'torsions', 'clashes', 'strain', 'unsat.', 'PB', 'clashscore'] : ['drift Å', 'clashes', 'strain', 'unsat.', 'clashscore', 'rama'];
    const physVal = (p) => lig ? [p.drift, p.torsions, p.clashes, p.strain, p.unsatisfied, p.pbPassed, p.clashscore] : [p.drift, p.clashes, p.strain, p.unsatisfied, p.clashscore, p.rama];
    const physRows = S.physics.map(p => ({ seed: `s${p.seed}`, color: (lig ? p.pbPassed < 20 : p.drift > 2) ? '#8E6420' : '#55554F', cells: physVal(p).map(v => ({ v: typeof v === 'number' ? (Number.isInteger(v) ? String(v) : v.toFixed(v < 10 ? 2 : 1)) : String(v) })) }));
    const physMedian = physHead.map((_, k) => { const st = this.stats(S.physics.map(p => physVal(p)[k])); return { v: st ? (Number.isInteger(st.median) ? String(st.median) : st.median.toFixed(2)) : '·' }; });
    const totalMs = r.sources.reduce((a, s) => a + s.ms, 0); const cached = r.sources.filter(s => s.cached).length;
    const fmtTime = (iso) => new Date(iso).toLocaleTimeString(undefined, { hour12: false });
    vals.rp = {
      name: rj.name, id: r.id, claim: r.claim, verdictLabel: vm.label, verdictColor: vm.color, taskName: r.taskName, tools: r.tools.map(t => t.name).join(' + '), toolsLong: r.tools.map(t => `${t.name} ${t.version}`).join(', '), target: r.inputs.target, reference: r.inputs.reference, seeds: r.inputs.seeds, date: new Date(r.createdAt).toLocaleString(undefined, { dateStyle: 'medium', timeStyle: 'short' }),
      layerNav: r.layers.map((l, i) => { const w = worst(l.checks); const p = l.checks.filter(c => c.result === 'pass').length, wn = l.checks.filter(c => c.result === 'warn').length, st = l.checks.filter(c => c.result === 'stop').length; return { name: l.name, summary: l.summary.join(' · '), select: () => this.setState({ reportLayer: i }), bar: li === i ? '#1A1A18' : '#E6E6E1', weight: li === i ? 600 : 500, color: li === i ? '#1A1A18' : '#55554F', dot: P[w], countsShort: `${p}/${wn}/${st}`, countsLong: `${p} pass${wn ? ` · ${wn} warn` : ''}${st ? ` · ${st} stop` : ''}` }; }),
      traceChecks: allChecks.length, traceMs: `${(r.layers.reduce((a, l) => a + l.durationMs, 0) / 1000).toFixed(1)} s`, toolVersions: r.tools.map(t => ({ line: `${t.name} ${t.version}` })),
      structChips: [{ id: 'crystal', label: r.inputs.reference }, { id: 'medoid', label: 'medoid' }, ...S.ensemble.filter(e => e.kind === 'seed').map(e => ({ id: e.id, label: e.label })), ...S.ensemble.filter(e => e.kind === 'docking' || e.kind === 'model').map(e => ({ id: e.id, label: e.label })), { id: 'overlay', label: 'overlay' }].map(c => ({ ...c, select: () => this.setState({ structSel: c.id }), bg: ss === c.id ? '#1A1A18' : 'transparent', color: ss === c.id ? '#fff' : '#55554F', border: ss === c.id ? '#1A1A18' : '#E6E6E1' })),
      structCaption: ss === 'crystal' ? `RCSB ${r.inputs.reference} · experimental` : ss === 'overlay' ? `${r.inputs.reference} + predicted · ${S.ensemble.length} structures` : selEnt ? `${selEnt.source} ${selEnt.label} · RMSD to medoid ${selEnt.rmsdToMedoid.toFixed(1)} Å` : '',
      col4: lig ? 'ipTM/CNN' : 'ipTM',
      ensembleRows: S.ensemble.map(e => { const id = e.kind === 'medoid' ? 'medoid' : e.id; const on = ss === id; return { label: e.kind === 'medoid' ? `${e.label} · medoid` : e.label, select: () => this.setState({ structSel: id }), bg: on ? '#F7F7F4' : 'transparent', dot: this.KIND[e.kind], labelColor: on ? '#1A1A18' : '#55554F', rmsd: e.kind === 'medoid' ? '—' : e.rmsdToMedoid.toFixed(1), rmsdColor: e.rmsdToMedoid > 2 && e.kind !== 'medoid' ? P.warn : '#1A1A18', plddt: e.pocketPlddt ?? '·', col4: e.iptm ?? e.cnn ?? '·', pb: e.posebusters != null ? `${e.posebusters}/20` : '·' }; }),
      clusterPop: lig ? `${r.inputs.seeds - 1}/${r.inputs.seeds} seeds` : `3/${r.inputs.seeds} seeds`, pairwise: `${S.pairwise.median.toFixed(1)} Å · IQR ${S.pairwise.iqr[0].toFixed(1)}–${S.pairwise.iqr[1].toFixed(1)}`, sitePlacement: S.sitePlacement, poseAccuracy: S.poseAccuracy,
      statCards: [{ title: lig ? 'Binding site' : 'Interface', rows: S.site.map(([k, v]) => ({ k, v })) }, { title: lig ? 'Pose' : 'Complex', rows: S.pose.map(([k, v]) => ({ k, v })) }, ...(r.docking ? [{ title: `Docking · ${r.docking.tool}`, rows: r.docking.rows.map(([k, v]) => ({ k, v })) }] : [{ title: 'Sampling', rows: [['site placement', S.sitePlacement], ['pose accuracy', S.poseAccuracy], ['pairwise RMSD', `${S.pairwise.median.toFixed(1)} Å median`], ['Kendall τ', '0.90']].map(([k, v]) => ({ k, v })) }])],
      layer: { name: L.name, duration: `${L.durationMs} ms`, checks: L.checks.map(c => ({ ...c, dot: c.result === 'reported' ? 'transparent' : resColor(c.result), dotBorder: resColor(c.result), color: resColor(c.result) })) },
      sideFigures: L.figures.map(([k, v]) => ({ k, v })), sideChecks: L.checks.map(c => ({ name: c.name, result: c.result, color: resColor(c.result), dot: c.result === 'reported' ? 'transparent' : resColor(c.result) })),
      hasPB: S.posebusters.length > 0, posebusters: S.posebusters.map(p => ({ ...p, dot: p.pass ? P.pass : P.stop })), pbSummary: `${S.posebusters.filter(p => p.pass).length}/${S.posebusters.length} tests · medoid pose`,
      physCols: physHead.length, physHead: physHead.map(name => ({ name })), physRows, physMedian,
      paeBlock: lig ? `pocket block ${S.metrics[1].value} mean` : `interface block ${S.metrics[1].value} mean`, paeIntra: 'intra-chain 1.4 Å · diagonal', paeTokens: lig ? '38 pocket residues × ligand tokens' : `${r.inputs.target} × ${r.inputs.partner}`,
      interNodes: inter, interList: inter, ligandLabel: lig ? (r.sources.find(s => s.source === 'PDB CCD')?.accession || 'LIG') : r.inputs.partner, interSummary: `${inter.filter(i => i.known).length}/${inter.length} seen in known complexes`,
      seedPts, seedCut: 40 + 2 / 8 * 310, ciX1: 40 + S.pairwise.ci95[0] / 8 * 310, ciW: Math.max(2, (S.pairwise.ci95[1] - S.pairwise.ci95[0]) / 8 * 310), pwMedian: S.pairwise.median.toFixed(2), pwIqr: `${S.pairwise.iqr[0].toFixed(2)}–${S.pairwise.iqr[1].toFixed(2)}`, pwCi: `${S.pairwise.ci95[0].toFixed(2)}–${S.pairwise.ci95[1].toFixed(2)}`, tau: r.task === 'affinity_ranking' ? '0.82' : '0.90',
      agreeN: S.agreement.length, agreeHead: S.agreement.map(a => ({ name: a.method })), agreeUnit: lig ? 'ligand RMSD Å · spyrmsd' : 'interface RMSD Å · DockQ',
      agreeRows: S.agreement.map(a => ({ method: a.method, cells: a.cells.map(c => { const t = Math.min(1, c.value / 8); return { value: c.value === 0 ? '—' : c.value.toFixed(1), weight: c.weight, bg: c.value === 0 ? '#F7F7F4' : t < 0.25 ? T.pass : t < 0.6 ? T.warn : T.stop, color: c.value === 0 ? '#B9B9B3' : t < 0.25 ? P.pass : t < 0.6 ? '#8E6420' : P.stop }; }) })),
      calibFlagged: calib('flagged'), calibPassed: calib('passed'), hasRoc: !!S.roc, rocPts: S.roc ? S.roc.map(p => `${40 + p.fpr * 270},${130 - p.tpr * 120}`).join(' ') : '', auc: S.auc, enrichment: S.enrichment, rocCaption: S.roc ? '; right, ROC of Boltz-2 affinity ranking against ChEMBL inactives' : '',
      metrics: S.metrics.map(m => ({ ...m, border: m.separate ? P.accent : '#EFEFEB', valueColor: m.separate ? '#8E6420' : '#1A1A18' })),
      hasPerturbation: S.perturbation.length > 0, perturbation: S.perturbation.map(p => ({ ...p, dot: p.ok ? P.pass : P.warn, color: p.ok ? '#55554F' : '#8E6420' })),
      thresholds: r.thresholds.map(t => ({ ...t, color: /borrowed|suspected/.test(t.level) ? '#8E6420' : P.pass })),
      controls: r.controls.map(c => ({ ...c, dot: c.status === 'sound' ? P.pass : P.stop })), outputs: r.outputs.map(name => ({ name })),
      keyNumbers: lig ? [{ value: S.metrics[8].value, label: 'PoseBusters', color: '#1A1A18' }, { value: S.metrics[0].value, label: 'pocket pLDDT', color: '#1A1A18' }, { value: S.metrics[2].value, label: 'ipTM', color: '#1A1A18' }, { value: `${r.inputs.seeds - 1}/${r.inputs.seeds}`, label: 'seeds in medoid cluster', color: '#1A1A18' }, { value: `${S.agreement[0].cells[1].value} Å`, label: `${S.agreement[0].method} vs ${S.agreement[1].method}`, color: '#1A1A18' }, { value: '71', label: 'pocket exposure', color: P.warn }]
        : [{ value: S.metrics[2].value, label: 'ipTM', color: P.warn }, { value: S.metrics[1].value, label: 'interface PAE', color: '#1A1A18' }, { value: S.metrics[4].value, label: 'pDockQ', color: '#1A1A18' }, { value: `3/${r.inputs.seeds}`, label: 'seeds in medoid cluster', color: '#1A1A18' }, { value: '11', label: 'paired MSA depth', color: P.stop }, { value: '6/12', label: 'decoy partners', color: P.stop }],
      provSummary: `${r.sources.length} objects · ${cached} cached · ${r.sources.length - cached} network · ${totalMs.toLocaleString()} ms`, sources: r.sources.map(s => ({ ...s, sha: s.sha256.slice(0, 12) + '…', time: fmtTime(s.retrievedAt), msColor: s.cached ? '#8B8B85' : '#1A1A18' })),
      recordLine: `run record ${r.id}.json · ${r.record.notebook} · seeds ${r.record.seeds.join(' ')}`, flagged,
    };
    // ----- ensemble view -----
    const maxV = this.props.gridViewers ?? 6;
    const cellStats = (e) => [{ k: 'RMSD', v: e.kind === 'medoid' ? '—' : `${e.rmsdToMedoid.toFixed(1)} Å`, color: e.rmsdToMedoid > 2 && e.kind !== 'medoid' ? P.warn : '#1A1A18' }, { k: 'pLDDT', v: e.pocketPlddt ?? '·', color: '#1A1A18' }, { k: lig ? 'ipTM/CNN' : 'ipTM', v: e.iptm ?? e.cnn ?? '·', color: '#1A1A18' }, { k: 'PB', v: e.posebusters != null ? `${e.posebusters}/20` : '·', color: '#1A1A18' }];
    const metricRow = (name, unit, vals2, fills) => { const st = this.stats(vals2); if (!st) return null; const span = (st.max - st.min) || 1; return { name, unit, pts: vals2.map((v, i) => ({ x: typeof v === 'number' ? 4 + (v - st.min) / span * 192 : -10, fill: fills[i] })), medX: 4 + (st.median - st.min) / span * 192, median: st.median.toFixed(2), mean: st.mean.toFixed(2), sd: st.sd.toFixed(2), min: st.min.toFixed(2), max: st.max.toFixed(2) }; };
    const ensFills = S.ensemble.map(e => this.KIND[e.kind]); const seedFills = S.seeds.map(() => this.KIND.seed);
    vals.en = view === 'ensemble' ? {
      count: S.ensemble.length,
      cells: S.ensemble.map((e, i) => { const id = e.kind === 'medoid' ? 'medoid' : e.id; return { label: e.kind === 'medoid' ? `${e.label} · medoid` : e.label, source: e.source, dot: this.KIND[e.kind], border: e.kind === 'medoid' ? P.accent : '#E6E6E1', live: i < maxV && vals.useMolstar, static: !(i < maxV && vals.useMolstar), ref: this.gridRef(e.id, id), stats: cellStats(e) }; }),
      summary: [metricRow('RMSD to medoid', 'Å', S.ensemble.filter(e => e.kind !== 'medoid').map(e => e.rmsdToMedoid), S.ensemble.filter(e => e.kind !== 'medoid').map(e => this.KIND[e.kind])), metricRow(lig ? 'Pocket pLDDT' : 'Interface pLDDT', '', S.ensemble.map(e => e.pocketPlddt), ensFills), metricRow('ipTM', '', S.ensemble.map(e => e.iptm), ensFills), ...(lig ? [metricRow('PoseBusters passed', '/20', S.ensemble.map(e => e.posebusters), ensFills), metricRow('Gnina CNN score', '', S.ensemble.map(e => e.cnn), ensFills)] : []), metricRow('Minimisation drift', 'Å', S.physics.map(p => p.drift), seedFills), metricRow('Torsion strain', 'kcal/mol', S.physics.map(p => p.strain), seedFills), metricRow('Clashscore', '', S.physics.map(p => p.clashscore), seedFills)].filter(Boolean),
    } : { cells: [], summary: [] };
    return vals;
  }
}

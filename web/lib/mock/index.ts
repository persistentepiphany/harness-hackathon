// Mock mode: the prototype's data and simulator (web/design/prototype/data/runs.js, logic-v2.js).
export * from './data';
export { Simulator, TICK_MS, SEED_BASE_TIME, type SimJob, type SimAgentTask, type SimulatorOptions } from './simulator';
export { createMockHarnessApi, type MockHarnessApi, type MockControls, type CreateMockOptions } from './mock-api';

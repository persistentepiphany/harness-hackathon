// Report blocks and figures. /documents imports these by name; keep the names and props stable.
// Every block takes ReportBlockProps ({record, tools?, variant?: 'screen' | 'print', className?})
// and shows a muted "not computed" in its slot when the record lacks its stats block.
export type { ReportBlockProps } from './types';
export { VerdictHeader, type VerdictHeaderProps } from './VerdictHeader';
export { StatCards } from './StatCards';
export { CheckTable, CheckRow, type CheckTableProps } from './CheckTable';
export { PoseBustersGrid } from './PoseBustersGrid';
export { SeedStatsTable } from './SeedStatsTable';
export { MetricsTable } from './MetricsTable';
export { StructureImage, type StructureImageProps } from './StructureImage';
export { ProvenanceTable } from './ProvenanceTable';
export { LayerSidebar, type LayerSidebarProps } from './LayerSidebar';
export { EnsembleTable, type EnsembleTableProps } from './EnsembleTable';
export { StructurePanel } from './StructurePanel';
export { FiguresPanel } from './FiguresPanel';
export { PerturbationList, ThresholdsList, ControlsList } from './ReportLists';
export { ReportPicker } from './ReportPicker';
export { ReportView, RecordGate, downloadRecord } from './ReportView';
export { PaeHeatmap, type PaeHeatmapProps } from './figures/PaeHeatmap';
export { InteractionDiagram, type InteractionDiagramProps } from './figures/InteractionDiagram';
export { SeedSpread, type SeedSpreadProps } from './figures/SeedSpread';
export { AgreementMatrix } from './figures/AgreementMatrix';
export { CalibrationCurve } from './figures/CalibrationCurve';
export { RocCurve } from './figures/RocCurve';
export type { FigureProps } from './figures/common';
export { paeFromStats, paeColor, type PaeData } from './figures/pae';
export { mockPae } from './figures/pae-mock';
export { seedAxisLabel, seedAxis, seedSpreadPoints } from '@/lib/selectors/report';

import type { Tool, UiRunRecord } from '@/lib/types';

/** Props shared by every report block: the UI record and, optionally, the tool register (GET /ui/tools). */
export interface ReportBlockProps {
  record: UiRunRecord;
  /** Tool register; record.tools[].outputs is used first, the register fills missing outputs. */
  tools?: Tool[] | null;
  /** `print` uses the compact A4 sizes of the document page; default `screen`. */
  variant?: 'screen' | 'print';
  className?: string;
}

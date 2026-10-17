import type { Metadata } from 'next';
import { DocumentsView } from '@/components/document';

export const metadata: Metadata = { title: 'Documents · Harness' };

export default function DocumentPage() {
  return <DocumentsView />;
}

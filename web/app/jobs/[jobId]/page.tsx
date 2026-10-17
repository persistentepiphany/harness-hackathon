'use client';

import { useParams } from 'next/navigation';
import { JobScreen } from '@/components/jobs/JobScreen';

export default function JobPage() {
  const params = useParams<{ jobId: string }>();
  const jobId = params?.jobId ? decodeURIComponent(params.jobId) : null;
  return <JobScreen key={jobId ?? ''} jobId={jobId} />;
}

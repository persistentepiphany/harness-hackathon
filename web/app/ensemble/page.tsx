'use client';

// /ensemble?runs=a,b,c: several runs side by side (components/ensemble/CompareView).
import { Suspense } from 'react';
import { CompareView } from '@/components/ensemble/CompareView';

export default function ComparePage() {
  return (
    <main className="mx-auto flex w-full max-w-[1280px] animate-fade-up flex-col gap-7 px-6 pt-11 pb-20" data-testid="page-compare">
      <Suspense fallback={null}>
        <CompareView />
      </Suspense>
    </main>
  );
}

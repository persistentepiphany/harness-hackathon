import Link from 'next/link';

export default function NotFound() {
  return (
    <main className="mx-auto w-full max-w-[1160px] px-6 pt-11 pb-20" data-testid="page-not-found">
      <h1 className="m-0 text-[18px] font-semibold tracking-[-0.01em]">Not found</h1>
      <p className="mt-2 text-ink2">
        No page at this address. <Link href="/jobs" className="underline">Jobs</Link>
      </p>
    </main>
  );
}

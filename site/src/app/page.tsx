import Link from "next/link";

export default function Home() {
  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-6">
      <div className="max-w-xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">
          Ireland in Data
        </h1>
        <p className="mt-4 text-lg leading-8 text-zinc-600">
          An open, evidence-based, reproducible digital observatory of the
          Irish healthcare system — every statistic, chart, and conclusion
          traceable to its original source and independently regenerable.
        </p>
        <Link
          href="/dashboard"
          className="mt-8 inline-flex items-center justify-center rounded-md bg-zinc-900 px-5 py-3 text-sm font-medium text-white hover:bg-zinc-700"
        >
          View the hospital waiting list dashboard
        </Link>
      </div>
    </div>
  );
}

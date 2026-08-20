import Link from "next/link";

const DASHBOARDS = [
  {
    href: "/dashboard",
    label: "Hospital waiting lists",
    description: "IPDC & OP waiting lists by hospital, specialty, and wait band",
    internal: true,
  },
  {
    href: "/education-dashboard.html",
    label: "Medicine access & cost",
    description:
      "GEM fees, medicine graduates by gender & nationality, post-graduation outcomes",
    internal: false,
  },
  {
    href: "/hse-workforce-dashboard.html",
    label: "HSE medical workforce",
    description:
      "Consultant & NCHD growth, vacant posts, doctor nationality, salary bands",
    internal: false,
  },
];

export default function Home() {
  return (
    <div className="flex flex-1 items-center justify-center bg-zinc-50 px-6 py-16">
      <div className="max-w-xl text-center">
        <h1 className="text-3xl font-semibold tracking-tight text-zinc-900">
          Ireland in Data
        </h1>
        <p className="mt-4 text-lg leading-8 text-zinc-600">
          An open, evidence-based, reproducible digital observatory of the
          Irish healthcare system — every statistic, chart, and conclusion
          traceable to its original source and independently regenerable.
        </p>

        <div className="mt-10 flex flex-col gap-3 text-left">
          {DASHBOARDS.map((d) =>
            d.internal ? (
              <Link
                key={d.href}
                href={d.href}
                className="rounded-lg border border-zinc-200 bg-white px-5 py-4 transition-colors hover:border-zinc-400"
              >
                <span className="block text-sm font-semibold text-zinc-900">
                  {d.label}
                </span>
                <span className="mt-0.5 block text-sm text-zinc-600">
                  {d.description}
                </span>
              </Link>
            ) : (
              <a
                key={d.href}
                href={d.href}
                className="rounded-lg border border-zinc-200 bg-white px-5 py-4 transition-colors hover:border-zinc-400"
              >
                <span className="block text-sm font-semibold text-zinc-900">
                  {d.label}
                </span>
                <span className="mt-0.5 block text-sm text-zinc-600">
                  {d.description}
                </span>
              </a>
            )
          )}
        </div>
      </div>
    </div>
  );
}

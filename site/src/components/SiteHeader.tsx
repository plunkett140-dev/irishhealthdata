import Link from "next/link";
import { Logo } from "@/components/Logo";

// The wordmark is real text, not baked into the logo image — the icon
// mark is self-contained (own opaque background) so it's safe on any
// page background, but text needs a color that can respond to the page's
// actual background. Uses the same text-zinc-900 convention as every
// other heading on the site (page.tsx, dashboard/page.tsx) rather than
// var(--foreground), so it stays consistent with the rest of the site —
// if/when dark-mode support is actually wired up site-wide, this falls
// into that same future sweep rather than needing special-case handling.
export function SiteHeader() {
  return (
    <header className="border-b border-zinc-200 bg-white">
      <div className="mx-auto flex max-w-4xl items-center gap-3 px-6 py-4">
        <Link href="/" className="flex items-center gap-3">
          <Logo className="h-10 w-10 sm:h-12 sm:w-12" />
          <span className="text-lg font-semibold tracking-tight text-zinc-900">
            Ireland in Data
          </span>
        </Link>
      </div>
    </header>
  );
}

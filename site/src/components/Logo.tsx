// Icon mark only (no wordmark) — same geometry as app/icon.svg (the
// favicon). Kept as an inline component rather than an <img> reference
// because Next.js serves app/icon.svg at a generated query-string URL,
// not a stable path. Self-contained: the green square is its own opaque
// backdrop, so this renders correctly on any page background without
// needing to know what that background is.
export function Logo({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 150 150"
      className={className}
      role="img"
      aria-label="Ireland in Data logo"
    >
      <rect width="150" height="150" rx="28" fill="#169B62" />
      <rect x="30" y="109" width="16" height="26" rx="3" fill="#FFFFFF" />
      <rect x="56" y="89" width="16" height="46" rx="3" fill="#FFFFFF" />
      <rect x="82" y="69" width="16" height="66" rx="3" fill="#FFFFFF" />
      <rect x="108" y="49" width="16" height="86" rx="3" fill="#FFFFFF" />
      <circle cx="116" cy="35" r="9" fill="#FF883E" />
    </svg>
  );
}

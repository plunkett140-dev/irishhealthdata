import type {
  HospitalData,
  ListType,
  Population,
  SpecialtyBreakdownData,
} from "@/lib/types";

// Last updated / Methodology / Known limitations used to repeat under
// every chart on the page (5 times over, identical text each time for a
// given list type/population). Shown once here instead — reactive to the
// current toggles, since "last updated" genuinely differs between
// IPDC/Outpatient and Adult/Child, so a single static blob covering every
// combination at once would either be wrong or unreadably long.

interface PageFooterProps {
  national: HospitalData;
  specialtyBreakdown: SpecialtyBreakdownData;
  listType: ListType;
  population: Population;
}

export function PageFooter({
  national,
  specialtyBreakdown,
  listType,
  population,
}: PageFooterProps) {
  const trendData = national.list_types[listType];
  const trendSeries = trendData.populations[population];
  const specialtyData = specialtyBreakdown.list_types[listType];
  const specialtySeries = specialtyData.populations[population];

  return (
    <footer className="mt-16 border-t border-zinc-200 pt-6 text-xs leading-relaxed text-zinc-500">
      <p>
        Source: {national.source} | Last updated:{" "}
        {trendSeries.last_updated ?? "n/a"}
      </p>
      <p className="mt-3">
        <span className="font-medium text-zinc-600">
          Methodology (trend &amp; breakdown charts):
        </span>{" "}
        {trendData.methodology_note}
      </p>
      <p className="mt-3">
        <span className="font-medium text-zinc-600">
          Methodology (specialty breakdown):
        </span>{" "}
        {specialtyData.methodology_note}
      </p>
      <p className="mt-3">
        <span className="font-medium text-zinc-600">Known limitations:</span>{" "}
        {trendData.known_limitations}
        {specialtySeries.known_limitations
          ? ` ${specialtySeries.known_limitations}`
          : ""}
      </p>
    </footer>
  );
}

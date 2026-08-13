import {
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartFooter } from "@/components/ChartFooter";
import { BUCKET_COLORS, COLOR_PRIMARY } from "@/lib/theme";
import type { HospitalData, Population } from "@/lib/types";

function formatDate(dateStr: string) {
  return new Date(dateStr).toLocaleDateString("en-IE", {
    year: "numeric",
    month: "short",
  });
}

interface WaitingListChartsProps {
  data: HospitalData;
  population: Population;
  titlePrefix: string;
}

export function WaitingListCharts({
  data,
  population,
  titlePrefix,
}: WaitingListChartsProps) {
  const { last_updated, series: rawSeries } = data.populations[population];

  if (rawSeries.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No {population} waiting-list data available for {titlePrefix}.
      </p>
    );
  }

  const series = rawSeries.map((point) => ({
    ...point,
    label: formatDate(point.date),
  }));

  return (
    <div className="flex flex-col gap-10">
      <section>
        <h2 className="text-lg font-semibold text-zinc-900">
          {titlePrefix}: Total IPDC Waiting List ({population})
        </h2>
        <div className="mt-4 h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ left: 10, right: 20 }}>
              <CartesianGrid stroke="#E5E5E5" strokeWidth={0.6} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "#1A1A1A" }}
                minTickGap={40}
              />
              <YAxis tick={{ fontSize: 11, fill: "#1A1A1A" }} />
              <Tooltip />
              <Line
                type="monotone"
                dataKey="total"
                name="Total waiting"
                stroke={COLOR_PRIMARY}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ChartFooter
          source={data.source}
          lastUpdated={last_updated ?? "n/a"}
          methodologyNote={data.methodology_note}
          knownLimitations={data.known_limitations}
        />
      </section>

      <section>
        <h2 className="text-lg font-semibold text-zinc-900">
          {titlePrefix}: Waiting List by Length of Wait ({population})
        </h2>
        <div className="mt-4 h-80 w-full">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={series} margin={{ left: 10, right: 20 }}>
              <CartesianGrid stroke="#E5E5E5" strokeWidth={0.6} />
              <XAxis
                dataKey="label"
                tick={{ fontSize: 11, fill: "#1A1A1A" }}
                minTickGap={40}
              />
              <YAxis tick={{ fontSize: 11, fill: "#1A1A1A" }} />
              <Tooltip />
              <Legend />
              <Line
                type="monotone"
                dataKey="under_6"
                name="Under 6 Months"
                stroke={BUCKET_COLORS["Under 6 Months"]}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="six_to_12"
                name="6-12 Months"
                stroke={BUCKET_COLORS["6-12 Months"]}
                strokeWidth={2}
                dot={false}
              />
              <Line
                type="monotone"
                dataKey="twelve_plus"
                name="12+ Months"
                stroke={BUCKET_COLORS["12+ Months"]}
                strokeWidth={2}
                dot={false}
              />
            </LineChart>
          </ResponsiveContainer>
        </div>
        <ChartFooter
          source={data.source}
          lastUpdated={last_updated ?? "n/a"}
          methodologyNote={data.methodology_note}
          knownLimitations={data.known_limitations}
        />
      </section>
    </div>
  );
}

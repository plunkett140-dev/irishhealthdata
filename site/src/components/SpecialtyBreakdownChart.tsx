import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { ChartFooter } from "@/components/ChartFooter";
import { BUCKET_COLORS } from "@/lib/theme";
import { LIST_TYPE_LABELS } from "@/lib/types";
import type { ListType, Population, SpecialtyBreakdownData } from "@/lib/types";

interface SpecialtyBreakdownChartProps {
  data: SpecialtyBreakdownData;
  listType: ListType;
  population: Population;
}

export function SpecialtyBreakdownChart({
  data,
  listType,
  population,
}: SpecialtyBreakdownChartProps) {
  const { items: rawItems } = data.list_types[listType].populations[population];
  const listTypeLabel = LIST_TYPE_LABELS[listType];

  if (rawItems.length === 0) {
    return (
      <p className="text-sm text-zinc-500">
        No {population} {listTypeLabel} specialty-level data available.
      </p>
    );
  }

  // Recharts draws vertical bar charts top-to-bottom in data order, so
  // reverse here to get the largest specialty at the top of the chart.
  const items = [...rawItems].reverse();

  return (
    <section>
      <h2 className="text-lg font-semibold text-zinc-900">
        National {listTypeLabel} Waiting List by Specialty ({population})
      </h2>
      <div className="mt-4 w-full" style={{ height: items.length * 32 + 70 }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={items}
            layout="vertical"
            margin={{ left: 10, right: 30, top: 5, bottom: 5 }}
          >
            <CartesianGrid stroke="#E5E5E5" strokeWidth={0.6} horizontal={false} />
            <XAxis type="number" tick={{ fontSize: 11, fill: "#1A1A1A" }} />
            <YAxis
              type="category"
              dataKey="specialty_name"
              width={150}
              tick={{ fontSize: 11, fill: "#1A1A1A" }}
            />
            <Tooltip />
            <Legend />
            <Bar
              dataKey="under_6"
              name="Under 6 Months"
              stackId="wait"
              fill={BUCKET_COLORS["Under 6 Months"]}
            />
            <Bar
              dataKey="six_to_12"
              name="6-12 Months"
              stackId="wait"
              fill={BUCKET_COLORS["6-12 Months"]}
            />
            <Bar
              dataKey="twelve_plus"
              name="12+ Months"
              stackId="wait"
              fill={BUCKET_COLORS["12+ Months"]}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <ChartFooter source={data.source} />
    </section>
  );
}

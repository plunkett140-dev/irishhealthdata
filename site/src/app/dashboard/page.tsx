"use client";

import { useEffect, useState } from "react";
import { SpecialtyBreakdownChart } from "@/components/SpecialtyBreakdownChart";
import { WaitingListCharts } from "@/components/WaitingListCharts";
import type {
  HospitalData,
  HospitalIndexEntry,
  ListType,
  Population,
  SpecialtyBreakdownData,
} from "@/lib/types";
import { LIST_TYPE_LABELS, LIST_TYPES, POPULATIONS } from "@/lib/types";

const DEFAULT_SLUG = "beaumont-hospital";

function SegmentedToggle<T extends string>({
  value,
  options,
  labels,
  onChange,
}: {
  value: T;
  options: T[];
  labels?: Record<T, string>;
  onChange: (v: T) => void;
}) {
  return (
    <div className="inline-flex rounded-md border border-zinc-300 bg-white p-0.5">
      {options.map((option) => (
        <button
          key={option}
          type="button"
          onClick={() => onChange(option)}
          className={`rounded px-3 py-1 text-sm font-medium transition-colors ${
            value === option
              ? "bg-zinc-900 text-white"
              : "text-zinc-600 hover:text-zinc-900"
          }`}
        >
          {labels ? labels[option] : option}
        </button>
      ))}
    </div>
  );
}

export default function DashboardPage() {
  const [listType, setListType] = useState<ListType>("ipdc");
  const [population, setPopulation] = useState<Population>("Adult");
  const [national, setNational] = useState<HospitalData | null>(null);
  const [specialtyBreakdown, setSpecialtyBreakdown] =
    useState<SpecialtyBreakdownData | null>(null);
  const [index, setIndex] = useState<HospitalIndexEntry[]>([]);
  const [selectedSlug, setSelectedSlug] = useState<string>(DEFAULT_SLUG);
  const [hospitalData, setHospitalData] = useState<HospitalData | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetch("/data/national.json")
      .then((res) => res.json())
      .then((data: HospitalData) => setNational(data));
  }, []);

  useEffect(() => {
    fetch("/data/national_by_specialty.json")
      .then((res) => res.json())
      .then((data: SpecialtyBreakdownData) => setSpecialtyBreakdown(data));
  }, []);

  useEffect(() => {
    fetch("/data/hospitals/index.json")
      .then((res) => res.json())
      .then((data: HospitalIndexEntry[]) => {
        setIndex(data);
        const hasDefault = data.some((h) => h.slug === DEFAULT_SLUG);
        setSelectedSlug(hasDefault ? DEFAULT_SLUG : data[0]?.slug ?? "");
      });
  }, []);

  useEffect(() => {
    if (!selectedSlug) return;
    setLoading(true);
    fetch(`/data/hospitals/${selectedSlug}.json`)
      .then((res) => res.json())
      .then((data: HospitalData) => {
        setHospitalData(data);
        setLoading(false);
      });
  }, [selectedSlug]);

  return (
    <div className="mx-auto w-full max-w-4xl px-6 py-10">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-zinc-900">
            Hospital Waiting List Dashboard
          </h1>
          <p className="mt-1 text-sm text-zinc-600">
            NTPF waiting list data — Inpatient/Day Case (IPDC) and
            Outpatient (OP).
          </p>
        </div>
        <div className="flex flex-col items-end gap-2">
          <SegmentedToggle
            value={listType}
            options={LIST_TYPES}
            labels={LIST_TYPE_LABELS}
            onChange={setListType}
          />
          <SegmentedToggle
            value={population}
            options={POPULATIONS}
            onChange={setPopulation}
          />
        </div>
      </div>

      <div className="mt-8">
        {national ? (
          <WaitingListCharts
            data={national}
            listType={listType}
            population={population}
            titlePrefix="National"
          />
        ) : (
          <p className="text-sm text-zinc-500">Loading national data...</p>
        )}

        <div className="mt-10">
          {specialtyBreakdown ? (
            <SpecialtyBreakdownChart
              data={specialtyBreakdown}
              listType={listType}
              population={population}
            />
          ) : (
            <p className="text-sm text-zinc-500">
              Loading specialty breakdown...
            </p>
          )}
        </div>
      </div>

      <hr className="my-12 border-zinc-200" />

      <div>
        <h2 className="text-xl font-semibold tracking-tight text-zinc-900">
          Drill down by hospital
        </h2>

        <div className="mt-4">
          <label
            htmlFor="hospital-select"
            className="block text-sm font-medium text-zinc-700"
          >
            Hospital
          </label>
          <select
            id="hospital-select"
            value={selectedSlug}
            onChange={(e) => setSelectedSlug(e.target.value)}
            className="mt-1 w-full max-w-md rounded-md border border-zinc-300 bg-white px-3 py-2 text-sm text-zinc-900 shadow-sm focus:border-blue-500 focus:outline-none"
          >
            {index.map((h) => (
              <option key={h.slug} value={h.slug}>
                {h.hospital_name}
              </option>
            ))}
          </select>
        </div>

        <div className="mt-8">
          {loading || !hospitalData ? (
            <p className="text-sm text-zinc-500">Loading...</p>
          ) : (
            <WaitingListCharts
              data={hospitalData}
              listType={listType}
              population={population}
              titlePrefix={hospitalData.hospital_name}
            />
          )}
        </div>
      </div>
    </div>
  );
}

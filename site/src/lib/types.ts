// Matches the JSON shape written by etl/export_dashboard_data.py.

export type Population = "Adult" | "Child";
export const POPULATIONS: Population[] = ["Adult", "Child"];

export type ListType = "ipdc" | "op";
export const LIST_TYPES: ListType[] = ["ipdc", "op"];
export const LIST_TYPE_LABELS: Record<ListType, string> = {
  ipdc: "Inpatient/Day Case",
  op: "Outpatient",
};

export interface HospitalIndexEntry {
  slug: string;
  hospital_name: string;
}

export interface WaitingListPoint {
  date: string; // YYYY-MM-DD
  total: number;
  under_6: number;
  six_to_12: number;
  twelve_plus: number;
}

export interface WaitingListSeries {
  last_updated: string | null;
  series: WaitingListPoint[];
}

export interface ListTypeWaitingListData {
  methodology_note: string;
  known_limitations: string;
  populations: Record<Population, WaitingListSeries>;
}

export interface HospitalData {
  hospital_name: string;
  slug: string;
  source: string;
  list_types: Record<ListType, ListTypeWaitingListData>;
}

export interface SpecialtyBreakdownItem {
  specialty_name: string;
  total: number;
  under_6: number;
  six_to_12: number;
  twelve_plus: number;
}

export interface SpecialtyBreakdownSeries {
  last_updated: string | null;
  known_limitations: string;
  items: SpecialtyBreakdownItem[];
}

export interface ListTypeSpecialtyBreakdown {
  methodology_note: string;
  populations: Record<Population, SpecialtyBreakdownSeries>;
}

export interface SpecialtyBreakdownData {
  source: string;
  list_types: Record<ListType, ListTypeSpecialtyBreakdown>;
}

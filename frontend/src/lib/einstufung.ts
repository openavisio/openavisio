// Shape of an Einstufung and the statutory module list (ADR 042). Shared by the
// API client and the views, so neither has to reach into the other.

export interface Einstufung {
  id: string;
  patient_id: string;
  pflegegrad: number | null;
  total_points: number | null;
  valid_from: string | null;
  valid_until: string | null;
  authority: string | null;
  file_reference: string | null;
  note: string | null;
  source: string;
  document_reference_id: string | null;
  module_mobility: number | null;
  module_cognitive: number | null;
  module_behaviour: number | null;
  module_self_care: number | null;
  module_therapy_demands: number | null;
  module_daily_life: number | null;
}

export interface Scale {
  total: number;
  grade: number | null;
  thresholds: { from: number; to: number; grade: number }[];
}

export type EinstufungInput = Partial<
  Pick<
    Einstufung,
    | "pflegegrad" | "total_points" | "valid_from" | "valid_until"
    | "authority" | "file_reference" | "note"
    | "module_mobility" | "module_cognitive" | "module_behaviour"
    | "module_self_care" | "module_therapy_demands" | "module_daily_life"
  >
>;

/** § 15 SGB XI, in the order the law numbers them. `cap` is the most a module can
 *  contribute to the total, which is what makes the bars comparable and what the
 *  backend validates against. */
export const MODULES = [
  { key: "module_mobility", cap: 10 },
  { key: "module_cognitive", cap: 15 },
  { key: "module_behaviour", cap: 15 },
  { key: "module_self_care", cap: 40 },
  { key: "module_therapy_demands", cap: 20 },
  { key: "module_daily_life", cap: 15 },
] as const satisfies readonly { key: keyof Einstufung; cap: number }[];

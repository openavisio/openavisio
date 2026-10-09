// ADR 047
export type Aging = "lasting" | "changeable" | "visit_only";
export const AGINGS: Aging[] = ["lasting", "changeable", "visit_only"];

export interface IntakeForm {
  id: string;
  patient_id: string;
  title: string | null;
  file_name: string | null;
  status: "reading" | "draft" | "released" | "failed";
  processing_error: string | null;
  created_at: string;
  released_at: string | null;
}

export interface IntakeItem {
  text: string;
  section: string | null;
  kind: "fact" | "judgement";
  aging: Aging;
  answer: string | null;
  origin: "record" | "history" | "document" | "caregiver" | null;
  sources: { text: string; segment: string | null }[];
  related: string[];
  fact_id: string | null;
  document: { id: string; file_name: string } | null;
  passage: string | null;
  confirmed: boolean;
  record_corrected: boolean;
}

export interface IntakeFormDetail extends IntakeForm {
  items: IntakeItem[];
}

export interface HistoryFact {
  id: string;
  question: string;
  answer: string;
  aging: Aging;
  confirmed_on: string;
  source: "caregiver" | "document";
  document_reference_id: string | null;
  intake_form_id: string | null;
}

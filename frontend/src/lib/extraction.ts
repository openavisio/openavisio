// The shape of DocumentReference.extraction_json, written by the aiservice; the backend stores it as a plain dict.

export type MentionedPerson = { name: string; role: string; institution?: string };

export type Appointment = {
  date?: string;
  time?: string;
  provider?: string;
  location?: string;
  purpose?: string;
  is_future?: boolean;
};

export type Observation = {
  type?: string;
  value?: string | number;
  unit?: string;
  category?: string;
  panel?: string;
  reference_range?: string;
};

export type Diagnosis = {
  name?: string;
  code_display?: string;
  severity?: string | null;
  status?: string;
  onset_date?: string | null;
  category?: string;
  reaction?: string;
  verification_status?: string;
  [key: string]: unknown;
};

export type Medication = { name?: string; medication_display?: string; dosage?: string; [key: string]: unknown };

/** A Kassenbescheid's Rechtsbehelfsbelehrung, ADR 041. deadline_date is computed by the backend. */
export type Decision = {
  decision_date?: string | null;
  deadline_months?: number | null;
  deadline_date?: string | null;
  authority?: string | null;
  file_reference?: string | null;
  subject?: string | null;
  grounds?: string | null;
};

export type ExtractionJson = {
  summary?: string;
  mentioned_persons?: MentionedPerson[];
  diagnoses?: Diagnosis[];
  medications?: Medication[];
  observations?: Observation[];
  appointments?: Appointment[];
  recommendations?: string[];
  decision?: Decision | null;
};

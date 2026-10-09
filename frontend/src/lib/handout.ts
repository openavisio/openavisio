// ADR 048
export interface HandoutEntry {
  id: string;
  text: string;
  detail: string | null;
  date: string | null;
  suspected: boolean;
  retold: boolean;
  items: { text: string; flag: string | null }[];
}

export const VARIANTS = ["doctors", "emergency", "steckbrief", "authorities"] as const;

export interface Handout {
  variant: string;
  missing: string[];
  patient: { name: string; birth_date: string | null };
  sections: { key: string; preselected: boolean; entries: HandoutEntry[] }[];
}

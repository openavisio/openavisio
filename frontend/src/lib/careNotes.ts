// ADR 048
export const CARE_NOTE_HEADINGS = ["communication", "eating_drinking", "sleep", "aids", "what_helps", "what_overwhelms"] as const;

export type CareNotes = Record<(typeof CARE_NOTE_HEADINGS)[number], string | null>;

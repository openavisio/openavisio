// The measurement vocabulary, in one place. `display` is the canonical English
// name that gets STORED as code_display, so the data stays language-neutral and a
// record entered in German still matches one entered in English. What the user
// reads comes from `measurementLabel` instead — including for rows already in the
// database, which is why the label is derived from `code` rather than trusted from
// code_display.
export const MEASUREMENT_TYPES = [
  { code: "body-weight", display: "Weight", unit: "kg" },
  { code: "body-height", display: "Height", unit: "cm" },
  { code: "head-circumference", display: "Head Circumference", unit: "cm" },
  { code: "blood-pressure-systolic", display: "Blood Pressure (systolic)", unit: "mmHg" },
  { code: "blood-pressure-diastolic", display: "Blood Pressure (diastolic)", unit: "mmHg" },
  { code: "body-temperature", display: "Temperature", unit: "°C" },
  { code: "oxygen-saturation", display: "Oxygen Saturation", unit: "%" },
  { code: "heart-rate", display: "Heart Rate", unit: "bpm" },
  { code: "bmi", display: "BMI", unit: "kg/m²" },
] as const;

const KNOWN: Set<string> = new Set(MEASUREMENT_TYPES.map((t) => t.code));

/** Translated name for a measurement code. Anything the pipeline extracted under a
 *  code we do not know keeps whatever the document called it. */
export function measurementLabel(
  t: (key: string) => string,
  code: string | null | undefined,
  fallback: string | null | undefined,
): string {
  if (code && KNOWN.has(code)) return t(`type.${code}`);
  return fallback || code || "";
}

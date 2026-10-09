import { Sparkles } from "lucide-react";
import { getTranslations } from "next-intl/server";

/** "This was read out by a machine, and machines misread."
 *
 * Everything on these screens — summaries, lab values, diagnoses, medications —
 * was extracted from a scan by an OCR model and a language model. Both make
 * mistakes: a comma slips, a unit is dropped, a value lands in the wrong row.
 * The caregiver has to know that what she sees is a *reading* of the letter, not
 * the letter (#117).
 *
 * It sits BELOW the data, in its own tinted box. Wedged into a header row it
 * looked like an accident and pushed the title around; above the data it is a
 * banner nobody reads after a week. Below, it reads as a footnote to what you
 * just looked at — which is exactly what it is.
 */
export async function AiNotice() {
  const t = await getTranslations("Ai");

  return (
    <aside className="mt-6 flex items-start gap-2.5 rounded-xl border border-amber-300/60 bg-amber-50/60 px-4 py-3 text-xs leading-relaxed text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-200/90">
      <Sparkles className="mt-0.5 size-4 shrink-0" />
      <p>{t("notice")}</p>
    </aside>
  );
}

import { formatDate } from "@/lib/utils";

type Translate = (key: string, values?: Record<string, string>) => string;
type DataSetPurpose = { data_set?: string | null; data_set_since?: string | null; data_set_domain?: string | null };

// "Test attempts since 01/01/2024" (ADR 064); t is the Sharing namespace, td the Development one
export function dataSetLabel(t: Translate, td: Translate, p: DataSetPurpose, locale: string): string {
  if (!p.data_set) return "";
  const parts = [t(`DataSet_${p.data_set}`)];
  if (p.data_set_domain) parts.push(td(`domains.${p.data_set_domain}`));
  if (p.data_set_since) parts.push(t("Since", { date: formatDate(p.data_set_since, locale) }));
  return parts.join(" · ");
}

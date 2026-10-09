import { getIntakeForm, getPatient } from "@/lib/api";
import { getLocale, getTranslations } from "next-intl/server";
import { formatDate } from "@/lib/utils";
import { PrintButton } from "./PrintButton";

// No AppLayout: this page is the answer sheet as it goes to the practice.
export default async function IntakeFormPrintPage({ params }: { params: Promise<{ id: string; formId: string }> }) {
  const { id, formId } = await params;
  const t = await getTranslations("IntakeForms");
  const locale = await getLocale();
  const [patient, form] = await Promise.all([getPatient(id).catch(() => null), getIntakeForm(formId).catch(() => null)]);
  if (!patient || !form) return <div className="p-8 text-muted-foreground">{t("NotFound")}</div>;

  return (
    <main className="mx-auto max-w-3xl bg-white p-8 text-sm text-black">
      <PrintButton label={t("Print")} />
      <h1 className="text-xl font-semibold">{t("PrintTitle", { name: `${patient.given_name} ${patient.family_name}` })}</h1>
      <p className="mb-6 text-gray-600">
        {[patient.birth_date && t("PrintBorn", { date: formatDate(patient.birth_date, locale) }), form.title,
          t("PrintAsOf", { date: formatDate(form.released_at ?? new Date().toISOString(), locale) })]
          .filter(Boolean).join(" · ")}
      </p>
      <dl>
        {form.items.map((item, i) => (
          <div key={i} className="break-inside-avoid">
            {item.section && item.section !== form.items[i - 1]?.section && (
              <h2 className="mb-2 mt-6 font-semibold uppercase tracking-wide">{item.section}</h2>
            )}
            <div className="border-b border-gray-300 py-2">
              <dt className="font-medium">{item.text}</dt>
              {/* an unconfirmed suggestion was never an answer */}
              <dd className="mt-1 min-h-5 whitespace-pre-wrap">{item.confirmed ? item.answer : null}</dd>
            </div>
          </div>
        ))}
      </dl>
    </main>
  );
}

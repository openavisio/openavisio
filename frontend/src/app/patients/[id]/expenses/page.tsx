import { AppLayout } from "@/components/layout/AppLayout";
import { getExpenses, getExpenseSummary, getPatient } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { AddExpensePanel } from "./AddExpensePanel";
import { ExpensesTable } from "./ExpensesTable";
import { AiNotice } from "@/components/AiNotice";

export default async function ExpensesPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const t = await getTranslations("Exp");
  // One round trip, not two: awaiting the patient first and the expenses after
  // serialised three API calls and pushed first paint past 5s on a cold box.
  const [patient, data] = await Promise.all([
    getPatient(id).catch(() => null),
    Promise.all([getExpenses(id), getExpenseSummary(id)]).catch(() => null),
  ]);
  const fetchError = data === null;
  const [expenses, summary] = data ?? [[], null];

  if (!patient) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">{t("NotFound")}</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <AddExpensePanel patientId={id}>
        <Breadcrumb
          crumbs={[{ label: `${patient.given_name} ${patient.family_name}`, href: `/patients/${id}` }]}
          current={t("Title")}
          className=""
        />
      </AddExpensePanel>

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          {t("LoadError")}
        </div>
      ) : expenses.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">{t("Empty")}</div>
      ) : (
        <ExpensesTable expenses={expenses} summary={summary} />
      )}
      {expenses.length > 0 && <AiNotice />}
    </AppLayout>
  );
}

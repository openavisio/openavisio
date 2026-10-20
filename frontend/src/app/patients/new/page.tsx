import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import Link from "next/link";
import { redirect } from "next/navigation";
import { getTranslations } from "next-intl/server";
import { NewPatientForm } from "./NewPatientForm";

export default async function NewPatientPage() {
  const role = ((await auth())?.user as any)?.role;
  if (role !== "admin" && role !== "manager") redirect("/patients");
  const t = await getTranslations("Patient");
  return (
    <AppLayout>
      <div className="flex items-center gap-2">
        <Link href="/patients" className="text-sm text-muted-foreground hover:text-foreground">
          {t("Title")}
        </Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-2xl font-semibold tracking-tight">{t("Create")}</h1>
      </div>

      <div className="rounded-xl border bg-card p-6 max-w-lg">
        <NewPatientForm />
      </div>
    </AppLayout>
  );
}

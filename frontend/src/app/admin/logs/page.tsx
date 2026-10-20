import { AppLayout } from "@/components/layout/AppLayout";
import { getTranslations } from "next-intl/server";
import { LogsClient } from "./LogsClient";

export default async function AdminLogsPage() {
  const t = await getTranslations("Nav");
  return (
    <AppLayout>
      <h1 className="text-xl font-bold">{t("Logs")}</h1>
      <LogsClient />
    </AppLayout>
  );
}

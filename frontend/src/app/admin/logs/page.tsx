import { AppLayout } from "@/components/layout/AppLayout";
import { LogsClient } from "./LogsClient";

export default function AdminLogsPage() {
  return (
    <AppLayout>
      <h1 className="text-xl font-bold">Logs</h1>
      <LogsClient />
    </AppLayout>
  );
}

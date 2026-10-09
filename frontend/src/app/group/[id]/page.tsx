import { AppLayout } from "@/components/layout/AppLayout";
import { getGroup, getGroupMembers, getGroupPatients, getPatients } from "@/lib/api";
import Link from "next/link";
import { MemberPanel } from "./MemberPanel";
import { PatientPanel } from "./PatientPanel";

export default async function GroupDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [group, members, patients, allPatients] = await Promise.all([
    getGroup(id).catch(() => null),
    getGroupMembers(id).catch(() => []),
    getGroupPatients(id).catch(() => []),
    getPatients().catch(() => []),
  ]);

  if (!group) {
    return (
      <AppLayout>
        <div className="text-center py-12 text-muted-foreground">Group not found.</div>
      </AppLayout>
    );
  }

  return (
    <AppLayout>
      <div className="flex items-center gap-2 mb-6">
        <Link href="/group" className="text-muted-foreground hover:text-foreground text-sm">
          Groups
        </Link>
        <span className="text-muted-foreground">/</span>
        <h1 className="text-xl font-bold">{group.name}</h1>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <MemberPanel groupId={id} members={members} />
        <PatientPanel groupId={id} patients={patients} allPatients={allPatients} />
      </div>
    </AppLayout>
  );
}

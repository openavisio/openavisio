import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getGroups } from "@/lib/api";
import Link from "next/link";
import { Users, AlertCircle } from "lucide-react";
import { CreateGroupButton } from "../admin/groups/CreateGroupButton";

export default async function GroupPage() {
  let groups: any[] = [], fetchError = false;
  const [session] = await Promise.all([
    auth(),
    getGroups().then((g) => { groups = g }).catch(() => { fetchError = true }),
  ]);
  const role = (session?.user as any)?.role;
  const canManage = role === "admin" || role === "manager";

  return (
    <AppLayout>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Groups</h1>
        {canManage && <CreateGroupButton />}
      </div>

      {fetchError ? (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          Failed to load groups. The server may be unavailable.
        </div>
      ) : groups.length === 0 ? (
        <div className="text-center py-12 text-muted-foreground">No groups found.</div>
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {groups.map((g: any) => (
            <Link
              key={g.id}
              href={`/group/${g.id}`}
              className="rounded-xl border bg-card p-5 hover:bg-accent transition-colors group"
            >
              <div className="flex items-center gap-3 mb-3">
                <div className="rounded-full bg-primary/10 p-2">
                  <Users className="h-5 w-5 text-primary" />
                </div>
                <div>
                  <div className="font-semibold group-hover:underline">{g.name}</div>
                  <div className="text-xs text-muted-foreground">{g.member_count ?? 0} members</div>
                </div>
              </div>
              {g.patient_count !== undefined && (
                <div className="text-xs text-muted-foreground">{g.patient_count} patients shared</div>
              )}
            </Link>
          ))}
        </div>
      )}
    </AppLayout>
  );
}

import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { getAdminUsers } from "@/lib/api";
import { formatDate } from "@/lib/utils";
import { AlertCircle } from "lucide-react";
import { InviteUserButton } from "../invitations/InviteUserButton";
import { UserActions } from "./UserActions";

export default async function AdminUsersPage() {
  const [session, usersResult] = await Promise.all([
    auth(),
    getAdminUsers().then((u) => ({ data: u, error: false })).catch(() => ({ data: [], error: true })),
  ]);
  const { data: users, error } = usersResult;
  const selfEmail = (session?.user as any)?.email;

  return (
    <AppLayout>
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Users</h1>
        <InviteUserButton />
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
          <AlertCircle className="size-4 shrink-0" />
          Failed to load users. The server may be unavailable.
        </div>
      )}

      <div className="rounded-xl border bg-card overflow-hidden">
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/50">
            <tr>
              <th className="px-4 py-3 text-left font-medium">Name / Email</th>
              <th className="px-4 py-3 text-left font-medium">Status</th>
              <th className="px-4 py-3 text-left font-medium">Joined</th>
              <th className="px-4 py-3 text-left font-medium">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {users.map((u: any) => {
              const name = [u.first_name, u.last_name].filter(Boolean).join(" ");
              return (
                <tr key={u.id} className="hover:bg-muted/30 transition-colors">
                  <td className="px-4 py-3">
                    <div className="font-medium">{name || u.email}</div>
                    {name && <div className="text-xs text-muted-foreground">{u.email}</div>}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${u.is_active ? "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300" : "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300"}`}>
                      {u.is_active ? "Active" : "Disabled"}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-muted-foreground text-xs">{formatDate(u.created_at)}</td>
                  <UserActions
                    userId={u.id}
                    currentRole={u.role}
                    isActive={u.is_active}
                    isSelf={u.email === selfEmail}
                    userEmail={u.email}
                  />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </AppLayout>
  );
}

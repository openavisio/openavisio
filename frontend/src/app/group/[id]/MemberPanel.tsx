"use client";

import { useState, useTransition } from "react";
import { UserPlus, Trash2, Copy, Check } from "lucide-react";
import { inviteMemberAction, removeMemberAction, updateMemberRoleAction } from "./actions";

const ROLES = ["viewer", "manager", "owner"];

function MemberRow({ member, groupId }: { member: any; groupId: string }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function remove() {
    startTransition(async () => {
      const r = await removeMemberAction(groupId, member.id);
      if (r.error) setError(r.error);
    });
  }

  function changeRole(role: string) {
    startTransition(async () => {
      const r = await updateMemberRoleAction(groupId, member.id, role);
      if (r.error) setError(r.error);
    });
  }

  return (
    <tr className="hover:bg-muted/30 transition-colors">
      <td className="px-4 py-3 font-medium text-sm">{member.user_email}</td>
      <td className="px-4 py-3">
        <select
          value={member.role}
          onChange={(e) => changeRole(e.target.value)}
          disabled={pending}
          className="rounded border px-2 py-0.5 text-xs bg-background focus:outline-none focus:ring-1 focus:ring-primary disabled:opacity-50"
        >
          {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
        </select>
      </td>
      <td className="px-4 py-3">
        <button
          onClick={remove}
          disabled={pending}
          className="flex items-center gap-1 text-xs text-destructive hover:text-destructive/80 disabled:opacity-50"
        >
          <Trash2 className="size-3.5" />
          {pending ? "…" : "Remove"}
        </button>
        {error && <p className="text-xs text-destructive mt-1">{error}</p>}
      </td>
    </tr>
  );
}

function InviteForm({ groupId }: { groupId: string }) {
  const [email, setEmail] = useState("");
  const [role, setRole] = useState("viewer");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [inviteUrl, setInviteUrl] = useState("");

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setInviteUrl("");
    startTransition(async () => {
      const r = await inviteMemberAction(groupId, email, role);
      if (r.error) {
        setError(r.error);
      } else if (r.invite_url) {
        const fullUrl = `${window.location.origin}${r.invite_url}`;
        setInviteUrl(fullUrl);
        setEmail("");
      }
    });
  }

  function copy() {
    navigator.clipboard.writeText(inviteUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="border-t pt-4 space-y-3">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Invite member</p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <form onSubmit={submit} className="flex flex-wrap gap-2 items-end">
        <div className="space-y-1">
          <label className="text-xs font-medium">Email</label>
          <input
            type="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="user@example.com"
            className="rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background w-52"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium">Role</label>
          <select
            value={role}
            onChange={(e) => setRole(e.target.value)}
            className="rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          >
            {ROLES.map((r) => <option key={r} value={r}>{r}</option>)}
          </select>
        </div>
        <button
          type="submit"
          disabled={pending}
          className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
        >
          <UserPlus className="size-3.5" />
          {pending ? "Generating…" : "Generate invite link"}
        </button>
      </form>
      {inviteUrl && (
        <div className="flex items-center gap-2 rounded-lg border bg-muted/50 px-3 py-2">
          <span className="text-xs text-muted-foreground truncate flex-1">{inviteUrl}</span>
          <button onClick={copy} className="flex items-center gap-1 text-xs font-medium shrink-0">
            {copied ? <Check className="size-3.5 text-green-600" /> : <Copy className="size-3.5" />}
            {copied ? "Copied" : "Copy"}
          </button>
        </div>
      )}
    </div>
  );
}

export function MemberPanel({ groupId, members }: { groupId: string; members: any[] }) {
  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm">Members</div>
      <div className="p-4 space-y-4">
        {members.length === 0 ? (
          <p className="text-sm text-muted-foreground">No members yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr>
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Email</th>
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">Role</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {members.map((m) => (
                  <MemberRow key={m.id} member={m} groupId={groupId} />
                ))}
              </tbody>
            </table>
          </div>
        )}
        <InviteForm groupId={groupId} />
      </div>
    </div>
  );
}

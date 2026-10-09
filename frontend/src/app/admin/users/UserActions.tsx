"use client";

import { useState, useTransition } from "react";
import { setRoleAction, setActiveAction } from "./actions";
import { EraseUserButton } from "./EraseUserButton";

const ROLES = ["user", "manager", "admin"];

export function UserActions({
  userId,
  currentRole,
  isActive,
  isSelf,
  userEmail,
}: {
  userId: string;
  currentRole: string;
  isActive: boolean;
  isSelf: boolean;
  userEmail: string;
}) {
  const [role, setRole] = useState(currentRole);
  const [active, setActive] = useState(isActive);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function handleRole(newRole: string) {
    setRole(newRole);
    startTransition(async () => {
      const result = await setRoleAction(userId, newRole);
      if (result.error) { setError(result.error); setRole(currentRole); }
    });
  }

  function handleToggleActive() {
    const next = !active;
    setActive(next);
    startTransition(async () => {
      const result = await setActiveAction(userId, next);
      if (result.error) { setError(result.error); setActive(active); }
    });
  }

  return (
    <td className="px-4 py-3">
      <div className="flex items-center gap-2">
        <select
          value={role}
          onChange={(e) => handleRole(e.target.value)}
          disabled={pending || isSelf}
          className="text-xs border rounded px-2 py-1 bg-background disabled:opacity-50"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>{r}</option>
          ))}
        </select>
        <button
          onClick={handleToggleActive}
          disabled={pending || isSelf}
          className={`text-xs px-2 py-1 rounded border transition-colors disabled:opacity-50
            ${active
              ? "text-red-600 border-red-200 hover:bg-red-50 dark:hover:bg-red-950"
              : "text-green-600 border-green-200 hover:bg-green-50 dark:hover:bg-green-950"
            }`}
        >
          {active ? "Disable" : "Enable"}
        </button>
        {!isSelf && <EraseUserButton userId={userId} userEmail={userEmail} />}
        {error && <span className="text-xs text-destructive">{error}</span>}
      </div>
    </td>
  );
}

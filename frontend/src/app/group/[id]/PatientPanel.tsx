"use client";

import { useState, useTransition } from "react";
import { Trash2, UserPlus } from "lucide-react";
import { assignPatientAction, removePatientAction } from "./actions";
import Link from "next/link";

function PatientRow({ patient, groupId }: { patient: any; groupId: string }) {
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  function remove() {
    startTransition(async () => {
      const r = await removePatientAction(patient.id, groupId);
      if (r.error) setError(r.error);
    });
  }

  return (
    <tr className="hover:bg-muted/30 transition-colors">
      <td className="px-4 py-3">
        <Link href={`/patients/${patient.id}`} className="font-medium text-sm hover:underline">
          {patient.given_name} {patient.family_name}
        </Link>
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

export function PatientPanel({
  groupId,
  patients,
  allPatients,
}: {
  groupId: string;
  patients: any[];
  allPatients: any[];
}) {
  const [selectedId, setSelectedId] = useState("");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");

  const assignedIds = new Set(patients.map((p) => p.id));
  const available = allPatients.filter((p) => !assignedIds.has(p.id));

  function assign() {
    if (!selectedId) return;
    setError("");
    startTransition(async () => {
      const r = await assignPatientAction(selectedId, groupId);
      if (r.error) setError(r.error);
      else setSelectedId("");
    });
  }

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm">Patients</div>
      <div className="p-4 space-y-4">
        {patients.length === 0 ? (
          <p className="text-sm text-muted-foreground">No patients assigned.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <tbody className="divide-y">
                {patients.map((p) => (
                  <PatientRow key={p.id} patient={p} groupId={groupId} />
                ))}
              </tbody>
            </table>
          </div>
        )}

        {available.length > 0 && (
          <div className="border-t pt-4 space-y-2">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">Add patient</p>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex gap-2">
              <select
                value={selectedId}
                onChange={(e) => setSelectedId(e.target.value)}
                className="rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background flex-1"
              >
                <option value="">Select a patient…</option>
                {available.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.given_name} {p.family_name}
                  </option>
                ))}
              </select>
              <button
                onClick={assign}
                disabled={pending || !selectedId}
                className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
              >
                <UserPlus className="size-3.5" />
                {pending ? "Adding…" : "Add"}
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

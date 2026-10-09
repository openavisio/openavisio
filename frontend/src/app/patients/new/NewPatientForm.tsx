"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { createPatientAction } from "./actions";

const GENDERS = [
  { value: "", label: "— not specified —" },
  { value: "male", label: "Male" },
  { value: "female", label: "Female" },
  { value: "other", label: "Other" },
];

export function NewPatientForm() {
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [givenName, setGivenName] = useState("");
  const [familyName, setFamilyName] = useState("");
  const [birthDate, setBirthDate] = useState("");
  const [gender, setGender] = useState("");
  const [identifier, setIdentifier] = useState("");
  const [error, setError] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    startTransition(async () => {
      const result = await createPatientAction({
        given_name: givenName,
        family_name: familyName,
        birth_date: birthDate || undefined,
        gender: gender || undefined,
        identifier: identifier || undefined,
      });
      if (result.error) {
        setError(result.error);
      } else {
        router.push(`/patients/${result.id}?created=1`);
      }
    });
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {error && (
        <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">{error}</div>
      )}

      <div className="grid grid-cols-2 gap-4">
        <div className="space-y-1.5">
          <label className="text-sm font-medium">
            First name <span className="text-destructive">*</span>
          </label>
          <input
            type="text"
            required
            value={givenName}
            onChange={(e) => setGivenName(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
        <div className="space-y-1.5">
          <label className="text-sm font-medium">
            Last name <span className="text-destructive">*</span>
          </label>
          <input
            type="text"
            required
            value={familyName}
            onChange={(e) => setFamilyName(e.target.value)}
            className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">Date of birth</label>
        <input
          type="date"
          value={birthDate}
          onChange={(e) => setBirthDate(e.target.value)}
          className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
        />
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">Gender</label>
        <select
          value={gender}
          onChange={(e) => setGender(e.target.value)}
          className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
        >
          {GENDERS.map((g) => (
            <option key={g.value} value={g.value}>{g.label}</option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label className="text-sm font-medium">Patient ID / reference number</label>
        <input
          type="text"
          value={identifier}
          onChange={(e) => setIdentifier(e.target.value)}
          placeholder="Optional internal identifier"
          className="w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
        />
      </div>

      <div className="flex items-center gap-3 pt-2">
        <button
          type="submit"
          disabled={pending}
          className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
        >
          {pending ? "Creating…" : "Create patient"}
        </button>
        <Link
          href="/patients"
          className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
        >
          Cancel
        </Link>
      </div>
    </form>
  );
}

"use client";

import { useEffect, useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { UserPlus, Trash2, ExternalLink, Link2, Copy, Check, Pencil, ChevronDown } from "lucide-react";
import { grantAccessAction, revokeAccessAction, createCaregiverInviteAction, updateAccessAction, listUserDirectoryAction } from "./access-actions";
import { formatDate } from "@/lib/utils";
import Link from "next/link";

const LEVEL_VALUES = ["view", "contribute", "full", "admin"] as const;

const RELATIONSHIPS: ({ value: string; k: string } | { group: string })[] = [
  { value: "", k: "NotSpecified" },
  { group: "grp_Family" },
  { value: "Father", k: "rel_Father" },
  { value: "Mother", k: "rel_Mother" },
  { value: "Son", k: "rel_Son" },
  { value: "Daughter", k: "rel_Daughter" },
  { value: "Sibling", k: "rel_Sibling" },
  { value: "Grandparent", k: "rel_Grandparent" },
  { value: "Spouse / Partner", k: "rel_SpousePartner" },
  { group: "grp_Professional" },
  { value: "Physician", k: "rel_Physician" },
  { value: "Nurse", k: "rel_Nurse" },
  { value: "Therapist", k: "rel_Therapist" },
  { value: "Social Worker", k: "rel_SocialWorker" },
  { value: "Care Worker", k: "rel_CareWorker" },
  { value: "__other__", k: "rel_Other" },
];

function LevelOptions() {
  const t = useTranslations("Access");
  return <>{LEVEL_VALUES.map((v) => <option key={v} value={v}>{t(`level_${v}`)}</option>)}</>;
}

function RelationshipSelect({
  value,
  onChange,
  className,
}: {
  value: string;
  onChange: (v: string) => void;
  className?: string;
}) {
  const t = useTranslations("Access");
  const isOther = value !== "" && !RELATIONSHIPS.find((r) => "value" in r && r.value === value && r.value !== "__other__");
  const [showCustom, setShowCustom] = useState(isOther);
  const [custom, setCustom] = useState(isOther ? value : "");

  function handleSelect(v: string) {
    if (v === "__other__") {
      setShowCustom(true);
      onChange(custom || "");
    } else {
      setShowCustom(false);
      onChange(v);
    }
  }

  const selectValue = showCustom ? "__other__" : value;

  return (
    <div className="flex gap-2">
      <select
        value={selectValue}
        onChange={(e) => handleSelect(e.target.value)}
        className={className}
      >
        {RELATIONSHIPS.map((r, i) =>
          "group" in r ? (
            <optgroup key={i} label={t(r.group)} />
          ) : (
            <option key={r.value} value={r.value}>{t(r.k)}</option>
          )
        )}
      </select>
      {showCustom && (
        <input
          type="text"
          value={custom}
          onChange={(e) => { setCustom(e.target.value); onChange(e.target.value); }}
          placeholder={t("DescribeRelationship")}
          className="flex-1 rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
        />
      )}
    </div>
  );
}

type Caregiver = {
  id: string;
  user_id: string;
  user_email: string;
  source: "direct" | "group";
  access_level?: string | null;
  relationship?: string | null;
  is_legal_representative?: boolean;
  granted_at?: string | null;
  expires_at?: string | null;
  purpose?: string | null;
  group_id?: string | null;
  group_name?: string | null;
  group_role?: string | null;
};

function DirectRow({ caregiver, patientId, currentUserEmail }: { caregiver: Caregiver; patientId: string; currentUserEmail?: string }) {
  const t = useTranslations("Access");
  const [editing, setEditing] = useState(false);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const router = useRouter();

  const [level, setLevel] = useState(caregiver.access_level ?? "view");
  const [relationship, setRelationship] = useState(caregiver.relationship ?? "");
  const [expires, setExpires] = useState(caregiver.expires_at ? caregiver.expires_at.slice(0, 10) : "");
  const [purpose, setPurpose] = useState(caregiver.purpose ?? "");
  const [isLegalRep, setIsLegalRep] = useState(!!caregiver.is_legal_representative);

  function save() {
    startTransition(async () => {
      const result = await updateAccessAction(caregiver.id, patientId, {
        access_level: level,
        expires_at: expires ? new Date(expires).toISOString() : null,
        purpose: purpose || null,
        relationship: relationship || null,
        is_legal_representative: isLegalRep,
      });
      if (result.error) setError(result.error);
      else setEditing(false);
    });
  }

  function revoke() {
    startTransition(async () => {
      const result = await revokeAccessAction(patientId, caregiver.id);
      if (result.error) { setError(result.error); return; }
      // revoking own access → the patient page would 404, leave it
      if (caregiver.user_email === currentUserEmail) router.push("/patients");
    });
  }

  if (editing) {
    return (
      <tr className="bg-muted/20">
        <td colSpan={6} className="px-4 py-3">
          <div className="space-y-3">
            <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">
              {t("EditAccess")} — {caregiver.user_email}
            </p>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
              <div className="space-y-1">
                <label className="text-xs font-medium">{t("Relationship")}</label>
                <RelationshipSelect
                  value={relationship}
                  onChange={setRelationship}
                  className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary"
                />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">{t("AccessLevel")}</label>
                <select value={level} onChange={(e) => setLevel(e.target.value)}
                  className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary">
                  <LevelOptions />
                </select>
                    </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">{t("Expires")}</label>
                <input type="date" value={expires} onChange={(e) => setExpires(e.target.value)}
                  className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <div className="space-y-1">
                <label className="text-xs font-medium">{t("Purpose")}</label>
                <input type="text" value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder={t("PurposePlaceholder")}
                  className="w-full rounded-lg border px-3 py-1.5 text-sm bg-background focus:outline-none focus:ring-2 focus:ring-primary" />
              </div>
              <label className="flex items-center gap-2 text-sm sm:col-span-2">
                <input type="checkbox" checked={isLegalRep} onChange={(e) => setIsLegalRep(e.target.checked)} />
                {t("LegalRep")}
              </label>
            </div>
            <div className="flex gap-2">
              <button onClick={save} disabled={pending}
                className="rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50">
                {pending ? t("Saving") : t("Save")}
              </button>
              <button onClick={() => { setEditing(false); setError(""); }}
                className="rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted">
                {t("Cancel")}
              </button>
            </div>
          </div>
        </td>
      </tr>
    );
  }

  return (
    <tr className="hover:bg-muted/30 transition-colors">
      <td className="px-4 py-3 font-medium text-sm">{caregiver.user_email}</td>
      <td className="px-4 py-3 text-sm text-muted-foreground">
        {caregiver.relationship || "—"}
        {caregiver.is_legal_representative && (
          <span className="ml-2 px-1.5 py-0.5 rounded text-[10px] font-medium bg-amber-100 text-amber-800 dark:bg-amber-950 dark:text-amber-300">{t("LegalRepBadge")}</span>
        )}
      </td>
      <td className="px-4 py-3">
        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-primary/10 text-primary capitalize">
          {caregiver.access_level}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">
        {caregiver.expires_at ? formatDate(caregiver.expires_at) : t("Never")}
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">{t("Direct")}</td>
      <td className="px-4 py-3">
        <div className="flex items-center gap-3">
          <button onClick={() => setEditing(true)}
            className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground">
            <Pencil className="size-3.5" /> {t("Edit")}
          </button>
          <button onClick={revoke} disabled={pending}
            className="flex items-center gap-1 text-xs text-destructive hover:text-destructive/80 disabled:opacity-50">
            <Trash2 className="size-3.5" /> {pending ? t("Revoking") : t("Revoke")}
          </button>
        </div>
        {error && <p className="text-xs text-destructive mt-1">{error}</p>}
      </td>
    </tr>
  );
}

function GroupRow({ caregiver }: { caregiver: Caregiver }) {
  const t = useTranslations("Access");
  return (
    <tr className="hover:bg-muted/30 transition-colors">
      <td className="px-4 py-3 font-medium text-sm">{caregiver.user_email}</td>
      <td className="px-4 py-3 text-xs text-muted-foreground">—</td>
      <td className="px-4 py-3">
        <span className="px-2 py-0.5 rounded-full text-xs font-medium bg-muted text-muted-foreground capitalize">
          {caregiver.group_role}
        </span>
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">—</td>
      <td className="px-4 py-3 text-xs">
        <Link
          href={`/group/${caregiver.group_id}`}
          className="flex items-center gap-1 text-primary hover:underline"
        >
          {caregiver.group_name}
          <ExternalLink className="size-3" />
        </Link>
      </td>
      <td className="px-4 py-3 text-xs text-muted-foreground">{t("ManagedInGroup")}</td>
    </tr>
  );
}

function GrantForm({ patientId }: { patientId: string }) {
  const t = useTranslations("Access");
  const [email, setEmail] = useState("");
  const [level, setLevel] = useState("view");
  const [relationship, setRelationship] = useState("");
  const [expires, setExpires] = useState("");
  const [purpose, setPurpose] = useState("");
  const [isLegalRep, setIsLegalRep] = useState(false);
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [directory, setDirectory] = useState<{ email: string; name?: string | null }[]>([]);

  useEffect(() => {
    listUserDirectoryAction().then(setDirectory).catch(() => {});
  }, []);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setSuccess("");
    startTransition(async () => {
      const result = await grantAccessAction(patientId, email, level, expires || undefined, purpose || undefined, relationship || undefined, isLegalRep);
      if (result.error) {
        setError(result.error);
      } else {
        setEmail(""); setExpires(""); setPurpose(""); setRelationship(""); setIsLegalRep(false);
        setSuccess(t("AccessGranted"));
        setTimeout(() => setSuccess(""), 3000);
      }
    });
  }

  return (
    <form onSubmit={submit} className="border-t pt-4 space-y-3">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("GrantDirectAccess")}</p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      {success && <p className="text-sm text-green-600 dark:text-green-400">{success}</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium">{t("User")}</label>
          <input
            type="email" required list="user-directory" value={email} onChange={(e) => setEmail(e.target.value)}
            placeholder={directory.length ? t("SelectOrType") : t("EmailPlaceholder")}
            className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
          <datalist id="user-directory">
            {directory.map((u) => (
              <option key={u.email} value={u.email}>{u.name ? `${u.name} — ${u.email}` : u.email}</option>
            ))}
          </datalist>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium">{t("Relationship")}</label>
          <RelationshipSelect
            value={relationship}
            onChange={setRelationship}
            className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium">{t("AccessLevel")}</label>
          <select
            value={level} onChange={(e) => setLevel(e.target.value)}
            className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          >
            <LevelOptions />
          </select>
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium">{t("ExpiresOptional")}</label>
          <input
            type="date" value={expires} onChange={(e) => setExpires(e.target.value)}
            className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
        <div className="space-y-1 sm:col-span-2">
          <label className="text-xs font-medium">{t("PurposeOptional")}</label>
          <input
            type="text" value={purpose} onChange={(e) => setPurpose(e.target.value)} placeholder={t("PurposePlaceholder")}
            className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
        <label className="flex items-center gap-2 text-sm sm:col-span-2">
          <input type="checkbox" checked={isLegalRep} onChange={(e) => setIsLegalRep(e.target.checked)} />
          {t("LegalRep")}
        </label>
      </div>
      <button
        type="submit" disabled={pending}
        className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
      >
        <UserPlus className="size-3.5" />
        {pending ? t("Granting") : t("GrantAccess")}
      </button>
    </form>
  );
}

function InviteForm({ patientId }: { patientId: string }) {
  const t = useTranslations("Access");
  const [email, setEmail] = useState("");
  const [level, setLevel] = useState("view");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [inviteUrl, setInviteUrl] = useState("");
  const [regUrl, setRegUrl] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  function submit(e: React.FormEvent) {
    e.preventDefault();
    setError(""); setInviteUrl(""); setRegUrl(null);
    startTransition(async () => {
      const result = await createCaregiverInviteAction(patientId, email || null, level);
      if (result.error) {
        setError(result.error);
      } else {
        const base = window.location.origin;
        setInviteUrl(base + result.invite_url);
        setRegUrl(result.registration_url ? base + result.registration_url : null);
      }
    });
  }

  function copy(url: string) {
    navigator.clipboard.writeText(url).then(() => { setCopied(true); setTimeout(() => setCopied(false), 2000); });
  }

  return (
    <form onSubmit={submit} className="border-t pt-4 space-y-3">
      <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide">{t("GenerateInviteLink")}</p>
      {error && <p className="text-sm text-destructive">{error}</p>}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium">{t("EmailOptional")}</label>
          <input
            type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="user@example.com"
            className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          />
        </div>
        <div className="space-y-1">
          <label className="text-xs font-medium">{t("AccessLevel")}</label>
          <select
            value={level} onChange={(e) => setLevel(e.target.value)}
            className="w-full rounded-lg border px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background"
          >
            <LevelOptions />
          </select>
        </div>
      </div>
      <button
        type="submit" disabled={pending}
        className="flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 disabled:opacity-50"
      >
        <Link2 className="size-3.5" />
        {pending ? t("Generating") : t("GenerateLink")}
      </button>
      {inviteUrl && (
        <div className="space-y-2 rounded-lg border bg-muted/30 p-3 text-sm">
          <div className="space-y-1">
            <p className="text-xs font-medium text-muted-foreground">{t("CaregiverInviteLink")}</p>
            <div className="flex items-center gap-2">
              <code className="flex-1 truncate text-xs">{inviteUrl}</code>
              <button type="button" onClick={() => copy(inviteUrl)} className="shrink-0 text-muted-foreground hover:text-foreground">
                {copied ? <Check className="size-3.5 text-green-600" /> : <Copy className="size-3.5" />}
              </button>
            </div>
          </div>
          {regUrl && (
            <div className="space-y-1 border-t pt-2">
              <p className="text-xs font-medium text-muted-foreground">{t("RegistrationLink")}</p>
              <div className="flex items-center gap-2">
                <code className="flex-1 truncate text-xs">{regUrl}</code>
                <button type="button" onClick={() => copy(regUrl!)} className="shrink-0 text-muted-foreground hover:text-foreground">
                  <Copy className="size-3.5" />
                </button>
              </div>
              <p className="text-xs text-muted-foreground">{t("RegistrationLinkHint")}</p>
            </div>
          )}
        </div>
      )}
    </form>
  );
}

function HandoverBanner({ patientId, caregivers, currentUserEmail }: { patientId: string; caregivers: Caregiver[]; currentUserEmail?: string }) {
  const t = useTranslations("Access");
  const [pending, startTransition] = useTransition();
  const [dismissed, setDismissed] = useState(false);
  const router = useRouter();

  const mine = caregivers.find(
    (c) => c.source === "direct" && c.access_level === "admin" && c.user_email === currentUserEmail
  );
  const otherAdmin = caregivers.some(
    (c) => c.access_level === "admin" && c.user_email !== currentUserEmail
  );
  const storageKey = `handoverDismissed:${patientId}`;
  useEffect(() => {
    setDismissed(localStorage.getItem(storageKey) === "1");
  }, [storageKey]);

  if (!mine || !otherAdmin || dismissed) return null;

  function completeHandover() {
    startTransition(async () => {
      const result = await revokeAccessAction(patientId, mine!.id);
      if (result?.error) return;
      // own access is gone — the patient page would 404, so leave it
      router.push("/patients");
    });
  }
  function dismiss() {
    localStorage.setItem(storageKey, "1");
    setDismissed(true);
  }

  return (
    <div className="rounded-lg border border-primary/40 bg-primary/5 px-4 py-3 text-sm flex flex-wrap items-center gap-3">
      <span>{t("HandoverMsg")}</span>
      <button onClick={completeHandover} disabled={pending}
        className="rounded-md bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium disabled:opacity-50">
        {pending ? t("Removing") : t("RemoveMyAccess")}
      </button>
      <button onClick={dismiss} className="text-muted-foreground hover:text-foreground text-xs">
        {t("KeepMyAccess")}
      </button>
    </div>
  );
}

export function AccessPanel({ patientId, caregivers, currentUserEmail }: { patientId: string; caregivers: Caregiver[]; currentUserEmail?: string }) {
  const t = useTranslations("Access");
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="rounded-xl border bg-card overflow-hidden">
      <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm">{t("Caregivers")}</div>
      <div className="p-4 space-y-4">
        <HandoverBanner patientId={patientId} caregivers={caregivers} currentUserEmail={currentUserEmail} />
        {caregivers.length > 0 ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="border-b">
                <tr>
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">{t("User")}</th>
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">{t("Relationship")}</th>
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">{t("LevelRole")}</th>
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">{t("Expires")}</th>
                  <th className="pb-2 text-left text-xs font-medium text-muted-foreground">{t("Source")}</th>
                  <th className="pb-2" />
                </tr>
              </thead>
              <tbody className="divide-y">
                {caregivers.map((c) =>
                  c.source === "group" ? (
                    <GroupRow key={c.id} caregiver={c} />
                  ) : (
                    <DirectRow key={c.id} caregiver={c} patientId={patientId} currentUserEmail={currentUserEmail} />
                  )
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t("NoCaregivers")}</p>
        )}

        <div className="border-t pt-3">
          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm font-medium hover:bg-muted/50 transition-colors"
          >
            <span className="flex items-center gap-2">
              <UserPlus className="size-4 text-muted-foreground" />
              {t("GrantAccess")}
            </span>
            <ChevronDown className={`size-4 text-muted-foreground transition-transform ${expanded ? "rotate-180" : ""}`} />
          </button>
          {expanded && (
            <div className="mt-3 space-y-0">
              <GrantForm patientId={patientId} />
              <InviteForm patientId={patientId} />
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { useTranslations } from "next-intl";
import { Check, ChevronDown, ChevronRight, Pencil } from "lucide-react";
import { decideCorrespondentProposals, decideDevelopmentProposals, decideDiagnosisProposals } from "@/lib/api";
import type { Review, ReviewGroup, ReviewKind, Spelling } from "@/lib/proposals";
import { formatDate } from "@/lib/utils";

const keyOf = (g: ReviewGroup) => g.spellings.map((s) => s.ids[0]).join();

const HEADINGS: Record<ReviewKind, string> = {
  correspondent: "Correspondents", diagnosis: "Diagnoses", ability: "Abilities", test_attempt: "TestAttempts",
};
const PREFIX: Record<ReviewKind, string> = { correspondent: "Correspondent", diagnosis: "", ability: "Ability", test_attempt: "TestAttempt" };

export function ProposalReview({ patientId, correspondents, diagnoses, abilities, tests }: {
  patientId: string; correspondents: Review | null; diagnoses: Review | null; abilities?: Review | null; tests?: Review | null;
}) {
  const t = useTranslations("ProposalReview");
  return (
    <div className="space-y-8">
      <div className="space-y-1 text-sm text-muted-foreground">
        <p>{t("Intro")}</p>
        <p>{t("IntroHow")}</p>
      </div>
      {correspondents && <Section kind="correspondent" patientId={patientId} review={correspondents} />}
      {diagnoses && <Section kind="diagnosis" patientId={patientId} review={diagnoses} />}
      {/* ADR 063: only when a therapy report proposed something; most families get none */}
      {!!abilities?.groups.length && <Section kind="ability" patientId={patientId} review={abilities} />}
      {!!tests?.groups.length && <Section kind="test_attempt" patientId={patientId} review={tests} />}
    </div>
  );
}

function Section({ kind, patientId, review }: { kind: ReviewKind; patientId: string; review: Review }) {
  const t = useTranslations("ProposalReview");
  // "gehört nicht dazu" moves a spelling into a card of its own, here in the browser
  const [groups, setGroups] = useState(review.groups);
  const [later, setLater] = useState<Set<string>>(new Set());

  function split(group: ReviewGroup, spelling: Spelling) {
    setGroups((gs) => gs.flatMap((g) => g !== group ? [g] : [
      { ...g, spellings: g.spellings.filter((s) => s !== spelling) },
      { record: null, suggested_name: spelling.name, spellings: [spelling] },
    ]));
  }

  const shown = groups.filter((g) => !later.has(keyOf(g)));
  return (
    <section className="space-y-4">
      <div>
        <h2 className="font-semibold">{t(HEADINGS[kind])}</h2>
        {kind !== "diagnosis" && <p className="text-sm text-muted-foreground">{t(`${HEADINGS[kind]}Intro`)}</p>}
      </div>
      {!review.grouped_by_model && (
        <p className="rounded-lg bg-amber-500/10 px-4 py-3 text-sm">{t("NotGrouped")}</p>
      )}
      {shown.length === 0 && <p className="text-sm text-muted-foreground">{t(kind === "correspondent" ? "NoCorrespondentsOpen" : "NothingOpen")}</p>}
      {shown.map((g) => (
        <GroupCard key={keyOf(g)} kind={kind} patientId={patientId} group={g}
                   onSplit={(s) => split(g, s)} onLater={() => setLater((l) => new Set(l).add(keyOf(g)))} />
      ))}
      {later.size > 0 && (
        <button onClick={() => setLater(new Set())} className="text-sm text-primary hover:underline">
          {t("ShowLater", { count: later.size })}
        </button>
      )}
    </section>
  );
}

function GroupCard({ kind, patientId, group, onSplit, onLater }: {
  kind: ReviewKind; patientId: string; group: ReviewGroup; onSplit: (s: Spelling) => void; onLater: () => void;
}) {
  const t = useTranslations("ProposalReview");
  const router = useRouter();
  const [name, setName] = useState(group.suggested_name);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, startTransition] = useTransition();

  const letters = new Set(group.spellings.flatMap((s) => s.documents.map((d) => d.id))).size;
  const suspected = group.spellings.every((s) => s.provisional);
  const quoted = `„${name}“`;
  const renamed = !!group.record && name.trim() !== group.record.name;
  const prefix = PREFIX[kind];
  // an Ability already in the record keeps its name here; it is renamed on the Development page
  const renameable = !(kind === "ability" && group.record);

  function decide(accept: boolean) {
    setError(null);
    startTransition(async () => {
      try {
        const ids = group.spellings.flatMap((s) => s.ids);
        if (kind === "correspondent") {
          await decideCorrespondentProposals(patientId, { document_ids: ids, name, correspondent_id: group.record?.id ?? null });
        } else if (kind !== "diagnosis") {
          await decideDevelopmentProposals(patientId, kind === "ability" ? "abilities" : "test-attempts",
                                           { proposal_ids: ids, accept, name, ability_id: group.record?.id ?? null });
        } else {
          await decideDiagnosisProposals(patientId, { proposal_ids: ids, accept, name, condition_id: group.record?.id ?? null });
        }
        router.refresh();
      } catch {
        setError(t("SaveError"));
      }
    });
  }

  return (
    <div className="overflow-hidden rounded-xl border bg-card">
      <div className="border-b bg-muted/40 px-4 py-3">
        {editing ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <input
                value={name}
                onChange={(e) => setName(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && name.trim() && setEditing(false)}
                aria-label={t("Name")}
                autoFocus
                className="w-full rounded-md border bg-background px-3 py-1.5 text-lg font-semibold"
              />
              <button onClick={() => setEditing(false)} disabled={!name.trim()} aria-label={t("NameDone")}
                      className="rounded-md border bg-background p-2 disabled:opacity-50">
                <Check className="size-4" />
              </button>
            </div>
            <div className="flex flex-wrap gap-1.5">
              {[group.record?.name, ...group.spellings.map((s) => s.name)]
                .filter((n, i, all): n is string => !!n && n !== name && all.indexOf(n) === i)
                .map((n) => (
                  <button key={n} onClick={() => setName(n)}
                          className="rounded-full border bg-background px-2.5 py-0.5 text-xs hover:bg-muted">
                    {n}
                  </button>
                ))}
            </div>
          </div>
        ) : (
          <div className="flex items-start gap-2">
            <h3 className="flex-1 text-lg font-semibold leading-snug">{name}</h3>
            {renameable && (
              <button onClick={() => setEditing(true)} aria-label={t("Name")} title={t("Name")}
                      className="rounded-md p-1 text-muted-foreground hover:bg-muted hover:text-foreground">
                <Pencil className="size-4" />
              </button>
            )}
          </div>
        )}
        <p className="text-xs text-muted-foreground">{t(`${prefix}${group.record ? "InRecord" : "New"}`)}</p>
      </div>

      <div className="space-y-3 p-4">
      <div>
        <p className="mb-1 text-xs text-muted-foreground">{t("HowWritten", { count: letters })}</p>
        <ul className="divide-y rounded-lg border">
          {group.spellings.map((s) => (
            <SpellingRow key={s.name} patientId={patientId} spelling={s}
                         onSplit={group.spellings.length > 1 ? () => onSplit(s) : undefined} />
          ))}
        </ul>
      </div>

      {error && <p className="text-sm text-destructive">{error}</p>}
      {/* a decision while the name is half typed would store whatever stood there */}
      {editing && <p className="text-xs text-muted-foreground">{t("NameFirst")}</p>}
      <div className="flex flex-wrap gap-2">
        <button onClick={() => decide(true)} disabled={pending || editing || !name.trim()}
                className="rounded-md bg-primary px-3 py-1.5 text-sm text-primary-foreground disabled:opacity-50">
          {group.record ? t("Confirm") : t(`${prefix}YesAdd`)}
        </button>
        {!group.record && kind !== "correspondent" && (
          <button onClick={() => decide(false)} disabled={pending || editing}
                  className="rounded-md border px-3 py-1.5 text-sm disabled:opacity-50">
            {t("NoNotInRecord")}
          </button>
        )}
        <button onClick={onLater} disabled={pending} className="rounded-md px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted">
          {t("Later")}
        </button>
      </div>
      <p className="text-xs text-muted-foreground">
        {group.record
          ? t(`${prefix}${renamed ? "OutcomeRenamed" : "OutcomeSame"}`, { name: quoted, old: `„${group.record.name}“`, count: letters })
          : t(`${prefix}${suspected ? "OutcomeNewSuspected" : "OutcomeNew"}`, { name: quoted, count: letters })}
      </p>
      </div>
    </div>
  );
}

function SpellingRow({ patientId, spelling: s, onSplit }: { patientId: string; spelling: Spelling; onSplit?: () => void }) {
  const t = useTranslations("ProposalReview");
  const td = useTranslations("Handout.dev");
  // a report's sentence is the point of an Ability card, so it starts open
  const [open, setOpen] = useState(s.documents.some((d) => d.labels));
  const docs = [...s.documents].sort((a, b) => (b.issued_date ?? "").localeCompare(a.issued_date ?? ""));
  return (
    <li className="px-3 py-2 text-sm">
      <div className="flex items-center gap-2">
        <button onClick={() => setOpen((o) => !o)} className="flex min-w-0 flex-1 items-center gap-2 text-left">
          {open ? <ChevronDown className="size-4 shrink-0" /> : <ChevronRight className="size-4 shrink-0" />}
          <span className="min-w-0 flex-1 truncate">
            {s.name}
            {s.provisional && <span className="ml-2 rounded bg-muted px-1.5 text-xs">{t("Suspected")}</span>}
          </span>
          <span className="shrink-0 text-xs text-muted-foreground">{t("Letters", { count: new Set(s.documents.map((d) => d.id)).size })}</span>
        </button>
        {onSplit && (
          <button onClick={onSplit} className="shrink-0 text-xs text-primary hover:underline">{t("NotPart")}</button>
        )}
      </div>
      {open && (
        <ul className="mt-1 space-y-0.5 pl-6 text-xs">
          {docs.map((d) => (
            <li key={d.id}>
              <a href={`/patients/${patientId}/documents/${d.id}`} target="_blank" rel="noopener" className="text-primary hover:underline">
                {d.issued_date ? formatDate(d.issued_date) : t("NoDate")} · {d.label}
              </a>
              {!d.issued_date && d.file_name && <span className="text-muted-foreground"> · {d.file_name}</span>}
              {!!d.labels?.length && <span className="text-muted-foreground"> · {d.labels.map((l) => td(l)).join(", ")}</span>}
              {d.quote && <p className="mt-0.5 italic text-muted-foreground">„{d.quote}“</p>}
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

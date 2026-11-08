"use client";

import { useState, useTransition } from "react";
import Link from "next/link";
import { useLocale, useTranslations } from "next-intl";
import { useRouter } from "next/navigation";
import { ChevronDown, FileText, Pencil, Plus, Trash2 } from "lucide-react";
import {
  createAbilityObservation, createCorrespondent, createTestAttempt, deleteAbilityObservation, deleteTestAttempt,
  updateAbility, updateAbilityObservation, updateTestAttempt, type S,
} from "@/lib/api";
import { ageAt, cn, formatDate } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";

type Ability = S<"AbilityDto">;
type Observation = S<"AbilityObservationDto">;
type Attempt = S<"TestAttemptDto">;
type Domain = NonNullable<S<"AbilityIn">["domain"]>;
type Place = NonNullable<S<"AbilityObservationIn">["place"]>;
type Setting = NonNullable<S<"TestAttemptIn">["setting"]>;
type Outcome = S<"TestAttemptIn">["outcome"];

const DOMAINS: Domain[] = ["communication", "daily_living", "social", "motor", "learning"];
const PLACES: Place[] = ["home", "kita_school", "therapy", "out"];
const SETTINGS: Setting[] = ["clinic", "practice", "home", "kita_school"];
const OUTCOMES: Outcome[] = ["completed", "stopped", "refused", "not_attempted"];
// names only, as families and reports write them; no items, no scales (ADR 063)
const KNOWN_TESTS = ["Bayley-III", "Bayley-4", "Mullen (MSEL)", "SON-R 2-8", "SON-R 6-40", "Leiter-3", "WPPSI-IV", "WISC-V", "Vineland-3"];

const inputCls = "mt-1.5 block w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";
const thisMonth = () => new Date().toLocaleDateString("sv").slice(0, 7);

type ObsDraft = { id?: string; name: string; domain: Domain | ""; month: string; day: string; place: Place | ""; works: boolean; withHelp: boolean; note: string };
type AbilityDraft = { id: string; name: string; domain: Domain | "" };
type TestDraft = { id?: string; name: string; month: string; day: string; ranBy: string; setting: Setting | ""; duration: string; outcome: Outcome | ""; reason: string; documentId: string };

const split = (d: string) => ({ month: d.slice(0, 7), day: d.length > 7 ? String(Number(d.slice(8, 10))) : "" });
const join = (month: string, day: string) => (day ? `${month}-${day.padStart(2, "0")}` : month);
const norm = (name: string) => name.trim().replace(/\s+/g, " ").toLowerCase();

export function DevelopmentView({ patientId, birthDate, abilities, attempts, correspondents, documents, children }: {
  patientId: string; birthDate?: string | null; abilities: Ability[]; attempts: Attempt[];
  correspondents: { id: string; name: string }[]; documents: S<"DocumentDto">[]; children: React.ReactNode;
}) {
  const t = useTranslations("Development");
  const locale = useLocale();
  const router = useRouter();
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [obs, setObs] = useState<ObsDraft | null>(null);
  const [ability, setAbility] = useState<AbilityDraft | null>(null);
  const [test, setTest] = useState<TestDraft | null>(null);

  const when = (d: string) => d.length === 7 ? new Date(`${d}-15T12:00`).toLocaleDateString(locale, { month: "long", year: "numeric" }) : formatDate(d, locale);
  const age = (d: string) => {
    const a = ageAt(birthDate, d);
    if (!a) return null;
    return [a.y && t("AgeYears", { n: a.y }), a.m && t("AgeMonths", { n: a.m })].filter(Boolean).join(" ") || t("Newborn");
  };
  const docLabel = (d: S<"DocumentDto">) => [d.issued_date && formatDate(d.issued_date, locale), d.correspondent?.name ?? d.detected_provider, d.file_name].filter(Boolean).join(" · ");
  const known = new Map(abilities.map((a) => [a.name.toLowerCase(), a]));
  const groups = [...DOMAINS, null].map((dom) => [dom, abilities.filter((a) => (a.domain ?? null) === dom)] as const).filter(([, list]) => list.length);

  function run(job: () => Promise<unknown>, done: () => void) {
    setError("");
    startTransition(async () => {
      try {
        await job();
        done();
        router.refresh();
      } catch {
        setError(t("SaveError"));
      }
    });
  }

  const close = () => { setObs(null); setAbility(null); setTest(null); setConfirmDelete(false); setError(""); };

  function newObs(a?: Ability) {
    close();
    setObs({ name: a?.name ?? "", domain: (a?.domain as Domain) ?? "", month: thisMonth(), day: "", place: "", works: true, withHelp: false, note: "" });
  }
  function editObs(a: Ability, o: Observation) {
    close();
    setObs({ id: o.id, name: a.name, domain: (a.domain as Domain) ?? "", ...split(o.observed_on), place: (o.place as Place) ?? "",
             works: o.works, withHelp: o.with_help, note: o.note ?? "" });
  }
  function saveObs(e: React.FormEvent) {
    e.preventDefault();
    const d = obs!;
    const body: S<"AbilityObservationIn"> = { ability_name: d.name, domain: d.domain || null, observed_on: join(d.month, d.day),
                                              place: d.place || null, works: d.works, with_help: d.withHelp, note: d.note.trim() || null };
    run(() => (d.id ? updateAbilityObservation(d.id, body) : createAbilityObservation(patientId, body)), close);
  }
  function saveAbility(e: React.FormEvent) {
    e.preventDefault();
    const d = ability!;
    // server action errors arrive masked in production, so the 409 is caught here first
    const other = known.get(norm(d.name));
    if (other && other.id !== d.id) return setError(t("NameTaken"));
    run(() => updateAbility(d.id, { name: d.name, domain: d.domain || null }), close);
  }

  function newTest() {
    close();
    setTest({ name: "", month: thisMonth(), day: "", ranBy: "", setting: "", duration: "", outcome: "", reason: "", documentId: "" });
  }
  function editTest(a: Attempt) {
    close();
    setTest({ id: a.id, name: a.test_name, ...split(a.attempted_on), ranBy: a.correspondent_name ?? "", setting: (a.setting as Setting) ?? "",
              duration: a.duration_minutes?.toString() ?? "", outcome: a.outcome as Outcome, reason: a.reason ?? "", documentId: a.document_id ?? "" });
  }
  function saveTest(e: React.FormEvent) {
    e.preventDefault();
    const d = test!;
    run(async () => {
      const name = d.ranBy.trim();
      const c = name ? correspondents.find((x) => x.name.toLowerCase() === name.toLowerCase()) ?? await createCorrespondent(name) : null;
      const body: S<"TestAttemptIn"> = { test_name: d.name, attempted_on: join(d.month, d.day), correspondent_id: c?.id ?? null,
                                         setting: d.setting || null, duration_minutes: d.duration ? Number(d.duration) : null,
                                         outcome: d.outcome as Outcome, reason: d.reason.trim() || null, document_id: d.documentId || null };
      return d.id ? updateTestAttempt(d.id, body) : createTestAttempt(patientId, body);
    }, close);
  }

  const status = (o: Observation) => o.no_longer ? "no_longer" : !o.works ? "fails" : o.with_help ? "works_with_help" : "works";
  const pill = (o: Observation) => (
    <span className={cn("inline-flex shrink-0 rounded-full px-2 py-0.5 text-xs", {
      "bg-emerald-500/10 text-emerald-800 dark:text-emerald-300": o.works,
      "bg-muted text-muted-foreground": !o.works && !o.no_longer,
      "bg-amber-500/15 text-amber-800 dark:text-amber-300": o.no_longer,
    })}>{t(`status.${status(o)}`)}</span>
  );
  const obsMeta = (o: Observation) => [when(o.observed_on), o.place && t(`places.${o.place}`), o.source !== "family" && t(`sources.${o.source}`)].filter(Boolean).join(" · ");

  const deleteButton = (onDelete: () => void) => (
    <Button type="button" variant="outline" size="sm" disabled={pending} className="mr-auto text-destructive"
            onClick={() => confirmDelete ? onDelete() : setConfirmDelete(true)}>
      <Trash2 className="size-4" />{confirmDelete ? t("DeleteConfirm") : t("Delete")}
    </Button>
  );
  const footer = (onDelete?: () => void, valid = true) => (
    <DialogFooter>
      {onDelete && deleteButton(onDelete)}
      <Button type="button" variant="outline" size="sm" onClick={close} disabled={pending}>{t("Cancel")}</Button>
      <Button type="submit" size="sm" disabled={pending || !valid}>{pending ? t("Saving") : t("Save")}</Button>
    </DialogFooter>
  );
  const dateFields = (d: { month: string; day: string }, set: (v: { month: string; day: string }) => void) => (
    <div className="grid grid-cols-2 gap-3">
      <label className="block text-sm font-medium">{t("Month")}
        <input type="month" required value={d.month} max={thisMonth()} onChange={(e) => set({ ...d, month: e.target.value })} className={inputCls} />
      </label>
      <label className="block text-sm font-medium">{t("Day")}
        <input type="number" min={1} max={31} inputMode="numeric" value={d.day} placeholder={t("DayPlaceholder")} onChange={(e) => set({ ...d, day: e.target.value })} className={inputCls} />
      </label>
    </div>
  );
  const choice = (label: string, on: boolean, set: () => void) => (
    <button type="button" onClick={set} aria-pressed={on}
            className={cn("rounded-lg border px-3 py-2 text-sm", on ? "border-primary bg-primary/10 font-medium" : "bg-background")}>{label}</button>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {children}
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" onClick={newTest}><Plus className="size-4" />{t("AddTestAttempt")}</Button>
          <Button onClick={() => newObs()}><Plus className="size-4" />{t("AddObservation")}</Button>
        </div>
      </div>
      <p className="text-sm text-muted-foreground">{t("Intro")}</p>
      {error && !obs && !ability && !test && <p className="text-sm text-destructive">{error}</p>}

      <section className="rounded-xl border bg-card">
        <h2 className="border-b px-4 py-3 text-sm font-semibold">{t("Abilities")}</h2>
        {abilities.length === 0 ? <p className="px-4 py-8 text-center text-sm text-muted-foreground">{t("AbilitiesEmpty")}</p> : groups.map(([dom, list]) => (
          <div key={dom ?? "none"} className="border-b px-4 py-3 last:border-b-0">
            <div className="mb-1 text-xs font-medium text-muted-foreground">{dom ? t(`domains.${dom}`) : t("NoDomain")}</div>
            <ul className="divide-y">
              {list.map((a) => {
                const latest = a.observations[a.observations.length - 1];
                return (
                  <li key={a.id}>
                    <details className="group py-2">
                      <summary className="flex cursor-pointer list-none items-center gap-3 text-sm">
                        <span className="min-w-0 flex-1">
                          <span className="font-medium">{a.name}</span>
                          <span className="block text-xs text-muted-foreground">{obsMeta(latest)}</span>
                        </span>
                        {pill(latest)}
                        <ChevronDown className="size-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180" />
                      </summary>
                      <div className="mt-2 space-y-2 border-l-2 pl-3 sm:ml-1">
                        <div className="text-xs font-medium text-muted-foreground">{t("History")}</div>
                        <ul className="space-y-2">
                          {[...a.observations].reverse().map((o) => (
                            <li key={o.id} className="flex items-start gap-3 text-sm">
                              <div className="min-w-0 flex-1">
                                <div className="flex flex-wrap items-center gap-2">{pill(o)}<span className="text-muted-foreground">{obsMeta(o)}</span></div>
                                {o.note && <div className="mt-0.5 whitespace-pre-line">{o.note}</div>}
                                {o.document_id && (
                                  <Link href={`/patients/${patientId}/documents/${o.document_id}`} className="inline-flex items-center gap-1 text-xs underline">
                                    <FileText className="size-3" />{t("OpenReport")}
                                  </Link>
                                )}
                                <div className="text-xs text-muted-foreground">{t("EnteredBy", { name: o.entered_by })}</div>
                              </div>
                              {o.can_edit && (
                                <Button variant="outline" size="sm" onClick={() => editObs(a, o)} aria-label={t("EditObservation")} title={t("EditObservation")}>
                                  <Pencil className="size-4" />
                                </Button>
                              )}
                            </li>
                          ))}
                        </ul>
                        <div className="flex flex-wrap gap-2 pt-1">
                          <Button variant="outline" size="sm" onClick={() => newObs(a)}><Plus className="size-4" />{t("AddObservationTo")}</Button>
                          {a.can_edit && (
                            <Button variant="outline" size="sm" onClick={() => { close(); setAbility({ id: a.id, name: a.name, domain: (a.domain as Domain) ?? "" }); }}>
                              <Pencil className="size-4" />{t("EditAbility")}
                            </Button>
                          )}
                        </div>
                      </div>
                    </details>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </section>

      <section className="rounded-xl border bg-card">
        <div className="border-b px-4 py-3">
          <h2 className="text-sm font-semibold">{t("TestAttempts")}</h2>
          <p className="mt-0.5 text-xs text-muted-foreground">{t("TestAttemptsHint")}</p>
        </div>
        {attempts.length === 0 ? <p className="px-4 py-8 text-center text-sm text-muted-foreground">{t("TestAttemptsEmpty")}</p> : (
          <ul className="divide-y">
            {attempts.map((a) => {
              const then = age(a.attempted_on);
              return (
                <li key={a.id} className="flex items-start gap-3 px-4 py-3 text-sm">
                  <div className="min-w-0 flex-1 space-y-0.5">
                    <div className="text-xs text-muted-foreground">{when(a.attempted_on)}{then && <> · {t("AgeThen", { age: then })}</>}</div>
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-medium">{a.test_name}</span>
                      <span className="rounded-full bg-muted px-2 py-0.5 text-xs">{t(`outcomes.${a.outcome}`)}</span>
                    </div>
                    {a.reason && <div className="whitespace-pre-line">{a.reason}</div>}
                    <div className="text-muted-foreground">
                      {[a.correspondent_name, a.setting && t(`settings.${a.setting}`), a.duration_minutes != null && t("Minutes", { n: a.duration_minutes })].filter(Boolean).join(" · ")}
                    </div>
                    {a.medications.length > 0 && <div className="text-xs text-muted-foreground">{t("MedicationsThatDay", { names: a.medications.join(", ") })}</div>}
                    {a.document_id && (
                      <Link href={`/patients/${patientId}/documents/${a.document_id}`} className="inline-flex items-center gap-1 text-xs underline">
                        <FileText className="size-3" />{t("OpenReport")}
                      </Link>
                    )}
                    <div className="text-xs text-muted-foreground">{t("EnteredBy", { name: a.entered_by })}</div>
                  </div>
                  {a.can_edit && (
                    <Button variant="outline" size="sm" onClick={() => editTest(a)} aria-label={t("EditTestAttempt")} title={t("EditTestAttempt")}>
                      <Pencil className="size-4" />
                    </Button>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </section>

      <Dialog open={!!obs} onOpenChange={(v) => !pending && !v && close()}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          {obs && (
            <form onSubmit={saveObs}>
              <DialogHeader><DialogTitle>{obs.id ? t("EditObservation") : t("AddObservation")}</DialogTitle></DialogHeader>
              <div className="space-y-4 px-6 pt-5">
                <label className="block text-sm font-medium">{t("Ability")}
                  <input required value={obs.name} onChange={(e) => setObs({ ...obs, name: e.target.value })} maxLength={256}
                         list="ability-names" placeholder={t("AbilityPlaceholder")} className={inputCls} />
                  <datalist id="ability-names">{abilities.map((a) => <option key={a.id} value={a.name} />)}</datalist>
                </label>
                {!known.has(norm(obs.name)) && (
                  <label className="block text-sm font-medium">{t("Domain")}
                    <select value={obs.domain} onChange={(e) => setObs({ ...obs, domain: e.target.value as Domain | "" })} className={inputCls}>
                      <option value="">{t("NoDomain")}</option>
                      {DOMAINS.map((d) => <option key={d} value={d}>{t(`domains.${d}`)}</option>)}
                    </select>
                  </label>
                )}
                {dateFields(obs, (v) => setObs({ ...obs, ...v }))}
                <label className="block text-sm font-medium">{t("Place")}
                  <select value={obs.place} onChange={(e) => setObs({ ...obs, place: e.target.value as Place | "" })} className={inputCls}>
                    <option value="">{t("NotGiven")}</option>
                    {PLACES.map((p) => <option key={p} value={p}>{t(`places.${p}`)}</option>)}
                  </select>
                </label>
                <div>
                  <div className="text-sm font-medium">{t("Result")}</div>
                  <div className="mt-1.5 grid grid-cols-2 gap-2">
                    {choice(t("Works"), obs.works, () => setObs({ ...obs, works: true }))}{choice(t("Fails"), !obs.works, () => setObs({ ...obs, works: false }))}
                    {choice(t("Alone"), !obs.withHelp, () => setObs({ ...obs, withHelp: false }))}{choice(t("WithHelp"), obs.withHelp, () => setObs({ ...obs, withHelp: true }))}
                  </div>
                </div>
                <label className="block text-sm font-medium">{t("Note")}
                  <textarea value={obs.note} onChange={(e) => setObs({ ...obs, note: e.target.value })} rows={2} className={inputCls} />
                </label>
                {error && <p className="text-sm text-destructive">{error}</p>}
              </div>
              {footer(obs.id ? () => run(() => deleteAbilityObservation(obs.id!), close) : undefined, !!obs.name.trim() && !!obs.month)}
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!ability} onOpenChange={(v) => !pending && !v && close()}>
        <DialogContent>
          {ability && (
            <form onSubmit={saveAbility}>
              <DialogHeader><DialogTitle>{t("EditAbility")}</DialogTitle></DialogHeader>
              <div className="space-y-4 px-6 pt-5">
                <label className="block text-sm font-medium">{t("Ability")}
                  <input required value={ability.name} onChange={(e) => setAbility({ ...ability, name: e.target.value })} maxLength={256} className={inputCls} />
                </label>
                <label className="block text-sm font-medium">{t("Domain")}
                  <select value={ability.domain} onChange={(e) => setAbility({ ...ability, domain: e.target.value as Domain | "" })} className={inputCls}>
                    <option value="">{t("NoDomain")}</option>
                    {DOMAINS.map((d) => <option key={d} value={d}>{t(`domains.${d}`)}</option>)}
                  </select>
                </label>
                {error && <p className="text-sm text-destructive">{error}</p>}
              </div>
              {footer(undefined, !!ability.name.trim())}
            </form>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!test} onOpenChange={(v) => !pending && !v && close()}>
        <DialogContent className="max-h-[90vh] overflow-y-auto">
          {test && (
            <form onSubmit={saveTest}>
              <DialogHeader><DialogTitle>{test.id ? t("EditTestAttempt") : t("AddTestAttempt")}</DialogTitle></DialogHeader>
              <div className="space-y-4 px-6 pt-5">
                <label className="block text-sm font-medium">{t("TestName")}
                  <input required value={test.name} onChange={(e) => setTest({ ...test, name: e.target.value })} maxLength={256}
                         list="test-names" placeholder={t("TestNamePlaceholder")} className={inputCls} />
                  <datalist id="test-names">
                    {[...new Set([...attempts.map((a) => a.test_name), ...KNOWN_TESTS])].map((n) => <option key={n} value={n} />)}
                  </datalist>
                </label>
                {dateFields(test, (v) => setTest({ ...test, ...v }))}
                <label className="block text-sm font-medium">{t("Outcome")}
                  <select required value={test.outcome} onChange={(e) => setTest({ ...test, outcome: e.target.value as Outcome })} className={inputCls}>
                    <option value="" disabled>{t("ChooseOutcome")}</option>
                    {OUTCOMES.map((o) => <option key={o} value={o}>{t(`outcomes.${o}`)}</option>)}
                  </select>
                </label>
                <label className="block text-sm font-medium">{t("Reason")}
                  <textarea value={test.reason} onChange={(e) => setTest({ ...test, reason: e.target.value })} rows={2} className={inputCls} />
                </label>
                <label className="block text-sm font-medium">{t("RanBy")}
                  <input value={test.ranBy} onChange={(e) => setTest({ ...test, ranBy: e.target.value })} maxLength={256}
                         list="test-correspondents" placeholder={t("RanByPlaceholder")} className={inputCls} />
                  <datalist id="test-correspondents">{correspondents.map((c) => <option key={c.id} value={c.name} />)}</datalist>
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label className="block text-sm font-medium">{t("Setting")}
                    <select value={test.setting} onChange={(e) => setTest({ ...test, setting: e.target.value as Setting | "" })} className={inputCls}>
                      <option value="">{t("NotGiven")}</option>
                      {SETTINGS.map((s) => <option key={s} value={s}>{t(`settings.${s}`)}</option>)}
                    </select>
                  </label>
                  <label className="block text-sm font-medium">{t("Duration")}
                    <input type="number" min={0} inputMode="numeric" value={test.duration} onChange={(e) => setTest({ ...test, duration: e.target.value })} className={inputCls} />
                  </label>
                </div>
                <label className="block text-sm font-medium">{t("Report")}
                  <select value={test.documentId} onChange={(e) => setTest({ ...test, documentId: e.target.value })} className={inputCls}>
                    <option value="">{t("NoReport")}</option>
                    {documents.map((d) => <option key={d.id} value={d.id}>{docLabel(d)}</option>)}
                  </select>
                </label>
                {error && <p className="text-sm text-destructive">{error}</p>}
              </div>
              {footer(test.id ? () => run(() => deleteTestAttempt(test.id!), close) : undefined, !!test.name.trim() && !!test.month && !!test.outcome)}
            </form>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}

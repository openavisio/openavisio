"use client";

import { useEffect, useState, useTransition, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { ChevronLeft, ChevronRight, X, Plus, Pencil, Trash2, Pill, Check } from "lucide-react";
import { getCalendarFeed, getCalendarEvent, createCalendarEvent, updateCalendarEvent, deleteCalendarEvent } from "@/lib/api";

interface FeedItem {
  id: string;
  title: string;
  start: string;
  end: string | null;
  all_day: boolean;
  type: string;
  color: string;
  url?: string | null;
  developmental_domain?: string | null;
}

const DOMAINS = ["motor", "speech", "cognitive", "social"] as const;

// A deadline is a last date, not an appointment — ADR 041.
const CATEGORIES = ["appointment", "milestone", "deadline"] as const;

// The pill showed the raw category name, so a German record said "Deadline".
const TYPE_LABEL = (t: (k: string) => string, type: string) =>
  ({ appointment: "Appointment", milestone: "Milestone", deadline: "Deadline" }[type]
    ? t({ appointment: "Appointment", milestone: "Milestone", deadline: "Deadline" }[type]!)
    : type);
type EventCategory = (typeof CATEGORIES)[number];


const TYPE_PILL: Record<string, string> = {
  appointment: "bg-blue-100 text-blue-700 dark:bg-blue-900/30 dark:text-blue-300",
  milestone: "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-300",
  deadline: "bg-orange-100 text-orange-800 dark:bg-orange-900/30 dark:text-orange-300",
  incident: "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-300",
  diary: "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-300",
  medication: "bg-cyan-100 text-cyan-700 dark:bg-cyan-900/30 dark:text-cyan-300",
};

/** Age at which a milestone was achieved, from patient birth date and event date. */
function achievedAge(birth?: string | null, at?: string | null): { y: number; m: number } | null {
  if (!birth || !at) return null;
  const b = new Date(birth.slice(0, 10));
  const d = new Date(at.slice(0, 10));
  if (isNaN(b.getTime()) || isNaN(d.getTime()) || d < b) return null;
  let months = (d.getFullYear() - b.getFullYear()) * 12 + (d.getMonth() - b.getMonth());
  if (d.getDate() < b.getDate()) months -= 1;
  if (months < 0) return null;
  return { y: Math.floor(months / 12), m: months % 12 };
}

const inputCls =
  "w-full rounded-lg border px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary bg-background";

function toDateStr(d: Date): string {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

function formatDateTime(iso: string, allDay: boolean): string {
  if (allDay) return iso.slice(0, 10);
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return `${iso.slice(0, 10)} ${d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`;
}

function withDefaultTime(dateStr: string): string {
  return dateStr.length === 10 ? `${dateStr}T08:00` : dateStr;
}

export function CalendarGrid({ patientId, birthDate, initialMonth }: { patientId: string; birthDate?: string | null; initialMonth?: string }) {
  const router = useRouter();
  const today = new Date();
  const todayStr = toDateStr(today);

  const t = useTranslations("Calendar");
  const tc = useTranslations("DocDetail");  // class_* labels live with the detail page
  const tCommon = useTranslations("Common");
  const locale = useLocale();
  const monthName = (m: number) => new Date(2000, m, 1).toLocaleDateString(locale, { month: "long" });
  // 2001-01-01 was a Monday
  const WEEKDAYS = [0, 1, 2, 3, 4, 5, 6].map((i) => new Date(2001, 0, 1 + i).toLocaleDateString(locale, { weekday: "short" }));
  const ageLabel = (a: { y: number; m: number }) =>
    [a.y && t("AgeYears", { n: a.y }), a.m && t("AgeMonths", { n: a.m })].filter(Boolean).join(" ") || t("Newborn");
  // ?month=YYYY-MM makes a month linkable — the chat links dates it mentions here (#201)
  const start = /^\d{4}-\d{2}$/.test(initialMonth ?? "") ? initialMonth!.split("-") : null;
  const [year, setYear] = useState(start ? Number(start[0]) : today.getFullYear());
  const [month, setMonth] = useState(start ? Number(start[1]) - 1 : today.getMonth());
  const [items, setItems] = useState<FeedItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState(false);

  // Medication courses as bars across the days they were taken, not two lonely
  // "Rx start" / "Rx end" pills (#130). Off by default — it is extra ink.
  const [showMedBars, setShowMedBars] = useState(false);

  const [drawerMode, setDrawerMode] = useState<"detail" | "edit" | "create" | null>(null);
  const [selected, setSelected] = useState<FeedItem | null>(null);
  const [eventDetail, setEventDetail] = useState<any>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [pending, startTransition] = useTransition();
  const [mutError, setMutError] = useState("");

  // Shared form state (create + edit reuse the same fields)
  const [fTitle, setFTitle] = useState("");
  const [fStart, setFStart] = useState("");
  const [fEnd, setFEnd] = useState("");
  const [fAllDay, setFAllDay] = useState(false);
  const [fProvider, setFProvider] = useState("");
  const [fLocation, setFLocation] = useState("");
  const [fPurpose, setFPurpose] = useState("");
  const [fCategory, setFCategory] = useState<EventCategory>("appointment");
  const [fDomain, setFDomain] = useState("");

  const lastDate = new Date(year, month + 1, 0).getDate();

  function refetch(y = year, m = month) {
    const last = new Date(y, m + 1, 0).getDate();
    const from = `${y}-${String(m + 1).padStart(2, "0")}-01`;
    const to = `${y}-${String(m + 1).padStart(2, "0")}-${String(last).padStart(2, "0")}`;
    getCalendarFeed(patientId, { from, to })
      .then((data) => setItems(Array.isArray(data) ? data : []))
      .catch(() => {});
  }

  useEffect(() => {
    setLoading(true);
    setFetchError(false);
    const last = new Date(year, month + 1, 0).getDate();
    const from = `${year}-${String(month + 1).padStart(2, "0")}-01`;
    const to = `${year}-${String(month + 1).padStart(2, "0")}-${String(last).padStart(2, "0")}`;
    getCalendarFeed(patientId, { from, to })
      .then((data) => { setItems(Array.isArray(data) ? data : []); setLoading(false); })
      .catch(() => { setFetchError(true); setLoading(false); });
  }, [year, month, patientId]);

  const eventsByDay = useMemo(
    () =>
      items
        // a medication drawn as a bar must not ALSO sit in its start day's cell
        .filter((i) => !(showMedBars && i.type === "medication"))
        .reduce<Record<string, FeedItem[]>>((acc, item) => {
          const day = item.start.slice(0, 10);
          (acc[day] ??= []).push(item);
          return acc;
        }, {}),
    [items, showMedBars],
  );

  const medications = useMemo(
    () => items.filter((i) => i.type === "medication" && i.start),
    [items],
  );

  function prevMonth() {
    if (month === 0) { setYear((y) => y - 1); setMonth(11); }
    else setMonth((m) => m - 1);
  }
  function nextMonth() {
    if (month === 11) { setYear((y) => y + 1); setMonth(0); }
    else setMonth((m) => m + 1);
  }

  function closeDrawer() {
    setDrawerMode(null);
    setSelected(null);
    setEventDetail(null);
    setConfirmDelete(false);
    setMutError("");
  }

  function openDetail(item: FeedItem) {
    setSelected(item);
    setEventDetail(null);
    setConfirmDelete(false);
    setMutError("");
    // medication pills and document markers are informational — jump to their page
    if (item.url && (item.type === "medication" || item.type === "document")) {
      router.push(item.url);
      return;
    }
    setDrawerMode("detail");
    if (item.type === "appointment" || item.type === "milestone" || item.type === "deadline") {
      getCalendarEvent(item.id)
        .then((d) => setEventDetail(d))
        .catch(() => {});
    }
  }

  function openCreate(day: string) {
    setFTitle("");
    setFStart(withDefaultTime(day));
    setFEnd("");
    setFAllDay(false);
    setFProvider("");
    setFLocation("");
    setFPurpose("");
    setFCategory("appointment");
    setFDomain("");
    setMutError("");
    setDrawerMode("create");
  }

  function openEdit() {
    const detail = eventDetail;
    if (!detail) return;
    setFTitle(detail.title ?? "");
    setFAllDay(detail.all_day ?? false);
    setFStart(detail.all_day ? (detail.start_at ?? "").slice(0, 10) : (detail.start_at ?? "").slice(0, 16));
    setFEnd(detail.end_at ? (detail.all_day ? detail.end_at.slice(0, 10) : detail.end_at.slice(0, 16)) : "");
    setFProvider(detail.provider ?? "");
    setFLocation(detail.location ?? "");
    setFPurpose(detail.purpose ?? "");
    setFCategory(CATEGORIES.includes(detail.category as EventCategory) ? (detail.category as EventCategory) : "appointment");
    setFDomain(detail.developmental_domain ?? "");
    setMutError("");
    setDrawerMode("edit");
  }

  function handleAllDayToggle(checked: boolean) {
    setFAllDay(checked);
    if (checked) {
      setFStart((v) => v.slice(0, 10));
      setFEnd((v) => v.slice(0, 10));
    } else {
      setFStart((v) => withDefaultTime(v));
    }
  }

  function handleSave(e: React.FormEvent) {
    e.preventDefault();
    setMutError("");
    const body: any = {
      title: fTitle,
      start_at: fStart,
      all_day: fAllDay,
      category: fCategory,
      ...(fEnd ? { end_at: fEnd } : {}),
      ...(fProvider ? { provider: fProvider } : {}),
      ...(fLocation ? { location: fLocation } : {}),
      ...(fPurpose ? { purpose: fPurpose } : {}),
      ...(fCategory === "milestone" && fDomain ? { developmental_domain: fDomain } : {}),
    };
    startTransition(async () => {
      try {
        if (drawerMode === "create") {
          await createCalendarEvent(patientId, body);
        } else if (drawerMode === "edit" && selected) {
          await updateCalendarEvent(selected.id, body);
        }
        closeDrawer();
        refetch();
      } catch {
        setMutError(tCommon("SaveError"));
      }
    });
  }

  // Closing an event reuses the existing PUT: status is the only field that changes,
  // the rest is echoed back from the loaded detail. Anything but "scheduled" also
  // stops the reminders — that is the whole point at a deadline (ADR 041).
  function setStatus(next: "scheduled" | "done" | "cancelled") {
    const detail = eventDetail;
    if (!detail || !selected) return;
    setMutError("");
    startTransition(async () => {
      try {
        await updateCalendarEvent(selected.id, {
          title: detail.title,
          start_at: detail.start_at,
          all_day: detail.all_day ?? false,
          category: detail.category,
          status: next,
          ...(detail.end_at ? { end_at: detail.end_at } : {}),
          ...(detail.provider ? { provider: detail.provider } : {}),
          ...(detail.location ? { location: detail.location } : {}),
          ...(detail.purpose ? { purpose: detail.purpose } : {}),
          ...(detail.description ? { description: detail.description } : {}),
        });
        setEventDetail({ ...detail, status: next });
        refetch();
      } catch {
        setMutError(tCommon("SaveError"));
      }
    });
  }

  function handleDelete() {
    if (!confirmDelete) { setConfirmDelete(true); return; }
    if (!selected) return;
    startTransition(async () => {
      try {
        await deleteCalendarEvent(selected.id);
        setItems((prev) => prev.filter((i) => i.id !== selected.id));
        closeDrawer();
      } catch {
        setMutError(t("DeleteError"));
      }
    });
  }

  // Build grid cells
  const firstDay = new Date(year, month, 1);
  const startPad = (firstDay.getDay() + 6) % 7;
  const totalCells = Math.ceil((startPad + lastDate) / 7) * 7;
  const cells = Array.from({ length: totalCells }, (_, i) => {
    const cellDate = new Date(year, month, i - startPad + 1);
    const dateStr = toDateStr(cellDate);
    return {
      dateStr,
      dayNum: cellDate.getDate(),
      isCurrentMonth: cellDate.getMonth() === month,
      isToday: dateStr === todayStr,
      dayEvents: eventsByDay[dateStr] ?? [],
    };
  });

  // The file name is a scanner artefact ("img20240405_08273634.pdf"), never a
  // title. Same rule as the documents list: say what it is and who wrote it.
  const KNOWN_CLASS = new Set([
    "lab_report", "doctor_letter", "therapy_report",
    "prescription", "imaging_report", "discharge_summary",
  ]);

  function eventLabel(ev: FeedItem): string {
    if (ev.type !== "document") return ev.title;
    const cls = (ev as any).classification as string | undefined;
    const label = cls && KNOWN_CLASS.has(cls) ? tc(`class_${cls}`) : null;
    if (label && ev.title && ev.title !== label) return `${label} · ${ev.title}`;
    return label ?? ev.title;
  }

  // The feed is sorted newest-first; an agenda reads forwards.
  const agenda = [...items].sort((a, b) => a.start.localeCompare(b.start));

  // A bar is cut into one segment per week row: CSS grid cannot span a row break.
  // An open-ended (still active) medication runs to the end of the visible month —
  // it does not stop, it just leaves the picture.
  const weeks = Array.from({ length: cells.length / 7 }, (_, w) => cells.slice(w * 7, w * 7 + 7));

  function barsForWeek(week: typeof cells) {
    const weekStart = week[0].dateStr;
    const weekEnd = week[6].dateStr;
    return medications
      .map((m) => {
        const start = m.start.slice(0, 10);
        // ongoing means "still taken today", not "will be taken forever" — the bar
        // stops at today and stays open on the right
        const end = (m.end ?? todayStr).slice(0, 10);
        if (start > weekEnd || end < weekStart) return null;
        const from = start < weekStart ? weekStart : start;
        const to = end > weekEnd ? weekEnd : end;
        const col = week.findIndex((c) => c.dateStr === from) + 1;
        const span = week.findIndex((c) => c.dateStr === to) - (col - 1) + 1;
        return {
          item: m,
          col,
          span,
          continuesLeft: start < weekStart,
          continuesRight: end > weekEnd,
          ongoing: !m.end,
        };
      })
      .filter(Boolean) as {
        item: FeedItem; col: number; span: number;
        continuesLeft: boolean; continuesRight: boolean; ongoing: boolean;
      }[];
  }

  return (
    <div>
      {/* Month navigation */}
      <div className="flex items-center justify-between mb-4">
        <div className="flex items-center gap-2">
          <button
            onClick={prevMonth}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors"
            aria-label={t("PrevMonth")}
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
          <span className="text-base font-semibold w-44 text-center">
            {monthName(month)} {year}
          </span>
          <button
            onClick={nextMonth}
            className="p-1.5 rounded-lg hover:bg-muted transition-colors"
            aria-label={t("NextMonth")}
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
        <div className="flex items-center gap-3">
          {/* off by default: the bars are extra ink, and most days you want the events */}
          <label className="flex cursor-pointer items-center gap-2 text-sm text-muted-foreground">
            <input
              type="checkbox"
              checked={showMedBars}
              onChange={(e) => setShowMedBars(e.target.checked)}
            />
            <Pill className="size-3.5" style={{ color: "#3f8c7d" }} />
            {t("MedBars")}
          </label>

          <button
            onClick={() => openCreate(todayStr)}
            className="inline-flex items-center gap-1.5 rounded-lg bg-primary text-primary-foreground px-3 py-1.5 text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="h-4 w-4" />
            {t("AddEvent")}
          </button>
        </div>
      </div>

      {/* Weekday headers */}
      <div className="grid grid-cols-7 mb-0.5">
        {WEEKDAYS.map((d) => (
          <div key={d} className="text-xs font-medium text-muted-foreground text-center py-1">
            {d}
          </div>
        ))}
      </div>

      {/* Grid */}
      {loading ? (
        <div className="h-96 flex items-center justify-center text-muted-foreground text-sm">
          {tCommon("Loading")}
        </div>
      ) : fetchError ? (
        <div className="h-96 flex items-center justify-center text-destructive text-sm">
          {t("LoadError")}
        </div>
      ) : (
        <div className="border-l border-t rounded-xl overflow-hidden">
          {weeks.map((week, wi) => {
            const bars = showMedBars ? barsForWeek(week) : [];
            return (
              <div key={wi}>
                {/* medication lane: one row of bars above the week's days */}
                {bars.length > 0 && (
                  <div className="grid grid-cols-7 gap-y-0.5 border-b bg-muted/10 px-0.5 py-1">
                    {bars.map((b) => (
                      <button
                        key={`bar-${b.item.id}-${wi}`}
                        onClick={() => openDetail(b.item)}
                        style={{
                          gridColumn: `${b.col} / span ${b.span}`,
                          backgroundColor: b.item.color,
                        }}
                        title={`${b.item.title}${b.ongoing ? ` — ${t("Ongoing")}` : ""}`}
                        className={`mx-0.5 truncate px-2 py-0.5 text-left text-xs font-medium text-white transition-opacity hover:opacity-80 ${
                          b.continuesLeft ? "rounded-l-none" : "rounded-l-full"
                        } ${b.continuesRight ? "rounded-r-none" : "rounded-r-full"}`}
                      >
                        <Pill className="mr-1 inline size-3 shrink-0 align-[-2px]" />
                        {b.item.title}
                      </button>
                    ))}
                  </div>
                )}

                <div className="grid grid-cols-7">
                  {week.map(({ dateStr, dayNum, isCurrentMonth, isToday, dayEvents }) => (
                    <div
                      key={dateStr}
                      className={`group border-r border-b min-h-[100px] p-1.5 ${isCurrentMonth ? "bg-card" : "bg-muted/20"}`}
                    >
                      <div className="flex items-center justify-between mb-1">
                        <span
                          className={`text-xs font-medium w-6 h-6 flex items-center justify-center rounded-full ${
                            isToday
                              ? "bg-primary text-primary-foreground"
                              : isCurrentMonth
                              ? "text-foreground"
                              : "text-muted-foreground"
                          }`}
                        >
                          {dayNum}
                        </span>
                        {isCurrentMonth && (
                          <button
                            onClick={() => openCreate(dateStr)}
                            className="opacity-0 group-hover:opacity-100 p-0.5 rounded hover:bg-muted transition-opacity"
                            aria-label={`Add event on ${dateStr}`}
                          >
                            <Plus className="h-3 w-3 text-muted-foreground" />
                          </button>
                        )}
                      </div>
                      <div className="space-y-0.5">
                        {dayEvents.slice(0, 3).map((ev) => (
                          <button
                            key={`${ev.type}-${ev.id}-${ev.start}`}
                            onClick={() => openDetail(ev)}
                            className={`w-full text-left px-1.5 py-0.5 rounded text-xs truncate font-medium ${
                              TYPE_PILL[ev.type] ?? "bg-muted text-muted-foreground"
                            }`}
                          >
                            {ev.type === "medication" && (
                              <Pill className="mr-1 inline size-3 shrink-0 align-[-2px]" />
                            )}
                            {eventLabel(ev)}
                          </button>
                        ))}
                        {dayEvents.length > 3 && (
                          <div className="text-xs text-muted-foreground px-1.5">
                            {t("More", { count: dayEvents.length - 3 })}
                          </div>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Agenda for the visible month — the grid shows WHEN, this shows WHAT.
          Cells hold three entries at most; here nothing is hidden behind "+2 more". */}
      {!loading && !fetchError && (
        <div className="mt-6">
          <h3 className="mb-2 text-sm font-semibold">{t("MonthList")}</h3>
          {agenda.length === 0 ? (
            <p className="rounded-xl border bg-card p-4 text-sm text-muted-foreground">{t("NoEvents")}</p>
          ) : (
            <ul className="divide-y rounded-xl border bg-card">
              {agenda.map((ev) => (
                <li key={`agenda-${ev.type}-${ev.id}-${ev.start}`}>
                  <button
                    onClick={() => openDetail(ev)}
                    className="flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors hover:bg-muted/40"
                  >
                    <span className="w-24 shrink-0 text-xs tabular-nums text-muted-foreground">
                      {ev.start.slice(8, 10)}.{ev.start.slice(5, 7)}.
                      {ev.end && ev.end !== ev.start && (
                        <> – {ev.end.slice(8, 10)}.{ev.end.slice(5, 7)}.</>
                      )}
                      {ev.type === "medication" && !ev.end && <> – {t("Ongoing")}</>}
                    </span>
                    <span className="size-2 shrink-0 rounded-full" style={{ backgroundColor: ev.color }} />
                    <span className="min-w-0 flex-1 truncate text-sm">
                      {ev.type === "medication" && (
                        <Pill className="mr-1 inline size-3.5 shrink-0 align-[-2px] text-muted-foreground" />
                      )}
                      {eventLabel(ev)}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      {/* Drawer overlay */}
      {drawerMode && (
        <>
          <div className="fixed inset-0 bg-black/40 z-40" onClick={closeDrawer} />
          <div className="fixed right-0 top-0 h-full w-full max-w-sm bg-background border-l shadow-xl z-50 flex flex-col">
            <div className="flex items-center justify-between px-4 py-3 border-b shrink-0">
              <span className="font-semibold text-sm">
                {drawerMode === "create"
                  ? t("NewEvent")
                  : drawerMode === "edit"
                  ? t("EditEvent")
                  : selected?.title}
              </span>
              <button
                onClick={closeDrawer}
                className="text-muted-foreground hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            </div>

            <div className="flex-1 overflow-y-auto p-4">
              {mutError && (
                <div className="rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm mb-4">
                  {mutError}
                </div>
              )}

              {/* Detail view */}
              {drawerMode === "detail" && selected && (
                <div className="space-y-4">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span
                      className={`px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
                        TYPE_PILL[selected.type] ?? "bg-muted text-muted-foreground"
                      }`}
                    >
                      {TYPE_LABEL(t, selected.type)}
                    </span>
                    <span className="text-sm text-muted-foreground">
                      {formatDateTime(selected.start, selected.all_day)}
                      {selected.end && !selected.all_day && ` – ${formatDateTime(selected.end, false)}`}
                    </span>
                  </div>

                  {eventDetail && (
                    <div className="space-y-2 text-sm">
                      {eventDetail.provider && (
                        <div>
                          <span className="text-muted-foreground">{t("Provider")}: </span>
                          {eventDetail.provider}
                        </div>
                      )}
                      {eventDetail.location && (
                        <div>
                          <span className="text-muted-foreground">{t("Location")}: </span>
                          {eventDetail.location}
                        </div>
                      )}
                      {eventDetail.purpose && (
                        <div>
                          <span className="text-muted-foreground">{t("Purpose")}: </span>
                          {eventDetail.purpose}
                        </div>
                      )}
                      {eventDetail.description && (
                        <div className="text-muted-foreground whitespace-pre-line">{eventDetail.description}</div>
                      )}
                    </div>
                  )}

                  {selected.type === "milestone" && (
                    <div className="space-y-2 text-sm">
                      {selected.developmental_domain && (
                        <div>
                          <span className="text-muted-foreground">{t("Domain")}: </span>
                          {(DOMAINS as readonly string[]).includes(selected.developmental_domain) ? t(`Domain_${selected.developmental_domain}`) : selected.developmental_domain}
                        </div>
                      )}
                      {achievedAge(birthDate, selected.start) && (
                        <div>
                          <span className="text-muted-foreground">{t("AchievedAt")}: </span>
                          {ageLabel(achievedAge(birthDate, selected.start)!)}
                        </div>
                      )}
                    </div>
                  )}

                  {eventDetail && selected.type !== "milestone" && (
                    <div className="flex items-center gap-2 flex-wrap pt-2 border-t">
                      {eventDetail.status === "scheduled" ? (
                        <>
                          <button
                            onClick={() => setStatus("done")}
                            disabled={pending}
                            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted transition-colors disabled:opacity-50"
                          >
                            <Check className="h-3.5 w-3.5" />
                            {t(selected.type === "deadline" ? "DeadlineMarkDone" : "MarkDone")}
                          </button>
                          <button
                            onClick={() => setStatus("cancelled")}
                            disabled={pending}
                            className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm text-muted-foreground hover:bg-muted transition-colors disabled:opacity-50"
                          >
                            {t(selected.type === "deadline" ? "DeadlineMarkCancelled" : "MarkCancelled")}
                          </button>
                        </>
                      ) : (
                        <>
                          <span className="inline-flex items-center gap-1.5 text-sm font-medium">
                            <Check className="h-3.5 w-3.5" />
                            {t(
                              selected.type === "deadline"
                                ? eventDetail.status === "done" ? "StatusDeadlineDone" : "StatusDeadlineCancelled"
                                : eventDetail.status === "done" ? "StatusDone" : "StatusCancelled",
                            )}
                          </span>
                          <button
                            onClick={() => setStatus("scheduled")}
                            disabled={pending}
                            className="text-xs text-primary hover:underline disabled:opacity-50"
                          >
                            {t("Reopen")}
                          </button>
                        </>
                      )}
                    </div>
                  )}

                  {(selected.type === "appointment" || selected.type === "milestone" || selected.type === "deadline") && (
                    <div className="flex items-center gap-2 pt-2">
                      <button
                        onClick={openEdit}
                        disabled={!eventDetail}
                        className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm hover:bg-muted transition-colors disabled:opacity-50"
                      >
                        <Pencil className="h-3.5 w-3.5" />
                        {tCommon("Edit")}
                      </button>
                      <button
                        onClick={handleDelete}
                        disabled={pending}
                        className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors disabled:opacity-50 ${
                          confirmDelete
                            ? "border-destructive bg-destructive text-destructive-foreground"
                            : "hover:border-destructive hover:bg-destructive/10 hover:text-destructive"
                        }`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                        {confirmDelete ? t("ConfirmDelete") : tCommon("Delete")}
                      </button>
                    </div>
                  )}
                </div>
              )}

              {/* Create / Edit form (shared) */}
              {(drawerMode === "create" || drawerMode === "edit") && (
                <form onSubmit={handleSave} className="space-y-3">
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      {t("EventTitle")} <span className="text-destructive">*</span>
                    </label>
                    <input
                      required
                      value={fTitle}
                      onChange={(e) => setFTitle(e.target.value)}
                      className={inputCls}
                      placeholder={t("TitlePlaceholder")}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">{tCommon("Type")}</label>
                    <select
                      value={fCategory}
                      onChange={(e) => setFCategory(e.target.value as EventCategory)}
                      className={inputCls}
                    >
                      <option value="appointment">{t("Appointment")}</option>
                      <option value="deadline">{t("Deadline")}</option>
                      <option value="milestone">{t("Milestone")}</option>
                    </select>
                  </div>
                  {fCategory === "milestone" && (
                    <div className="space-y-1.5">
                      <label className="text-sm font-medium">{t("DevDomain")}</label>
                      <select
                        value={fDomain}
                        onChange={(e) => setFDomain(e.target.value)}
                        className={inputCls}
                      >
                        <option value="">—</option>
                        {DOMAINS.map((d) => (
                          <option key={d} value={d}>{t(`Domain_${d}`)}</option>
                        ))}
                      </select>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="f-allday"
                      checked={fAllDay}
                      onChange={(e) => handleAllDayToggle(e.target.checked)}
                      className="rounded"
                    />
                    <label htmlFor="f-allday" className="text-sm">
                      {t("AllDay")}
                    </label>
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">
                      {t("StartDate")} <span className="text-destructive">*</span>
                    </label>
                    <input
                      required
                      type={fAllDay ? "date" : "datetime-local"}
                      value={fStart}
                      onChange={(e) => setFStart(e.target.value)}
                      className={inputCls}
                    />
                  </div>
                  <div className="space-y-1.5">
                    <label className="text-sm font-medium">{t("EndDate")}</label>
                    <input
                      type={fAllDay ? "date" : "datetime-local"}
                      value={fEnd}
                      onChange={(e) => setFEnd(e.target.value)}
                      className={inputCls}
                    />
                  </div>
                  {fCategory === "appointment" && (
                    <>
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium">{t("Provider")}</label>
                        <input
                          value={fProvider}
                          onChange={(e) => setFProvider(e.target.value)}
                          className={inputCls}
                          placeholder={t("ProviderPlaceholder")}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium">{t("Location")}</label>
                        <input
                          value={fLocation}
                          onChange={(e) => setFLocation(e.target.value)}
                          className={inputCls}
                          placeholder={t("LocationPlaceholder")}
                        />
                      </div>
                      <div className="space-y-1.5">
                        <label className="text-sm font-medium">{t("Purpose")}</label>
                        <input
                          value={fPurpose}
                          onChange={(e) => setFPurpose(e.target.value)}
                          className={inputCls}
                          placeholder={t("PurposePlaceholder")}
                        />
                      </div>
                    </>
                  )}
                  <div className="flex items-center gap-3 pt-1">
                    <button
                      type="submit"
                      disabled={pending}
                      className="rounded-lg bg-primary text-primary-foreground px-4 py-2 text-sm font-medium hover:bg-primary/90 disabled:opacity-50 transition-colors"
                    >
                      {pending ? tCommon("Saving") : tCommon("Save")}
                    </button>
                    <button
                      type="button"
                      onClick={drawerMode === "edit" ? () => setDrawerMode("detail") : closeDrawer}
                      className="rounded-lg border px-4 py-2 text-sm font-medium hover:bg-muted transition-colors"
                    >
                      {tCommon("Cancel")}
                    </button>
                  </div>
                </form>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}

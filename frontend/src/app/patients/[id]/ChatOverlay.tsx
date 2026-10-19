"use client";

import { Fragment, useEffect, useRef, useState, type ReactNode } from "react";
import { useSearchParams } from "next/navigation";
import Link from "next/link";
import { useTranslations } from "next-intl";
import { MessageCircle, Send, Siren, X } from "lucide-react";
type Message = { role: string; content: string; emergency_plan?: boolean };

type ChatAnswer = {
  answer: string;
  disclaimer: string;
  sources: { document_id: string; file_name: string }[];
  months: string[];
  emergency_plan: boolean;
};

const SUGGESTION_KEYS = ["s1", "s2", "s3", "s4"] as const;

const DATE_RE = /\b(\d{2})\.(\d{2})\.(\d{4})\b|\b(\d{4})-(\d{2})-(\d{2})\b/g;

/** Link dates in the answer to their calendar month — but only months that hold
 *  entries, a set the backend sends along (ADR 038). */
function withMonthLinks(text: string, patientId: string, months: string[]): ReactNode {
  if (!months.length) return text;
  const out: ReactNode[] = [];
  let last = 0;
  for (const m of text.matchAll(DATE_RE)) {
    const month = m[3] ? `${m[3]}-${m[2]}` : `${m[4]}-${m[5]}`;
    if (!months.includes(month)) continue;
    out.push(text.slice(last, m.index));
    out.push(
      <Link key={m.index} href={`/patients/${patientId}/calendar?month=${month}`} className="underline underline-offset-2 hover:text-primary">
        {m[0]}
      </Link>,
    );
    last = m.index + m[0].length;
  }
  out.push(text.slice(last));
  return out.map((n, i) => <Fragment key={i}>{n}</Fragment>);
}

export function ChatOverlay({ patientId, notice }: { patientId: string; notice: ReactNode }) {
  const t = useTranslations("Chat");
  const params = useSearchParams();
  const open = params.get("chat") === "1";

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [answer, setAnswer] = useState<ChatAnswer | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    fetch(`/api/patients/${patientId}/chat`)
      .then((r) => (r.ok ? r.json() : null))
      .then((h) => setMessages(h?.messages ?? []))
      .catch(() => {});
  }, [open, patientId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  // Native History API rather than router.push: pushState syncs with
  // useSearchParams without a server round trip, so ?chat=1 stays linkable and
  // the back button still closes the overlay — but opening it no longer
  // re-renders the page underneath and tears the panel out of the DOM.
  function setOpen(next: boolean) {
    const url = new URL(window.location.href);
    if (next) url.searchParams.set("chat", "1");
    else url.searchParams.delete("chat");
    window.history.pushState(null, "", url.pathname + url.search);
  }

  async function send(question: string) {
    if (!question.trim() || sending) return;
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setInput("");
    setSending(true);
    setError("");
    try {
      const res = await fetch(`/api/patients/${patientId}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      // An outage is not an answer: it gets its own line and is never stored.
      if (!res.ok) setError(t(res.status === 503 ? "Unavailable" : "Failed"));
      else {
        const data: ChatAnswer = await res.json();
        setAnswer(data);
        setMessages((prev) => [...prev, { role: "assistant", content: data.answer, emergency_plan: data.emergency_plan }]);
      }
    } catch {
      setError(t("Failed"));
    } finally {
      setSending(false);
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        aria-label={t("Title")}
        // above the MobileTabBar on mobile (ADR 030), bottom-right on desktop
        className="fixed bottom-20 right-4 z-40 flex size-14 print:hidden items-center justify-center rounded-full bg-primary text-primary-foreground shadow-lg transition-transform hover:scale-105 lg:bottom-6 lg:right-6"
      >
        <MessageCircle className="size-6" />
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex flex-col bg-card sm:inset-auto sm:bottom-6 sm:right-6 sm:h-[min(38rem,80vh)] sm:w-[26rem] sm:rounded-2xl sm:border sm:shadow-2xl">
      <div className="flex items-center justify-between border-b px-4 py-3">
        <h2 className="text-sm font-semibold">{t("Title")}</h2>
        <button onClick={() => setOpen(false)} aria-label={t("Close")} className="rounded-lg p-1.5 hover:bg-muted">
          <X className="size-5" />
        </button>
      </div>

      <div className="flex-1 space-y-4 overflow-y-auto p-4">
        {messages.length === 0 && (
          <div className="space-y-3">
            <p className="text-sm text-muted-foreground">{t("Empty")}</p>
            <div className="flex flex-wrap gap-2">
              {SUGGESTION_KEYS.map((k) => (
                <button
                  key={k}
                  onClick={() => send(t(`suggestions.${k}`))}
                  className="rounded-full border px-3 py-1.5 text-xs hover:bg-muted"
                >
                  {t(`suggestions.${k}`)}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[85%] whitespace-pre-wrap rounded-2xl px-4 py-2.5 text-sm ${
                msg.role === "user" ? "bg-primary text-primary-foreground" : "bg-muted text-foreground"
              }`}
            >
              {msg.role === "user" ? msg.content : withMonthLinks(msg.content, patientId, answer?.months ?? [])}
              {msg.emergency_plan && (
                <Link href={`/patients/${patientId}/emergency-plan`} data-testid="chat-emergency-plan"
                  className="mt-2 flex w-fit items-center gap-1.5 rounded-lg bg-red-500/10 px-3 py-1.5 font-medium text-red-700 hover:bg-red-500/20 dark:text-red-300">
                  <Siren className="size-4" />
                  {t("OpenEmergencyPlan")}
                </Link>
              )}
            </div>
          </div>
        ))}

        {/* A local 27b takes a minute per answer, so a static label reads as a
            hang. Three bouncing dots, stilled for prefers-reduced-motion. */}
        {sending && (
          <div className="flex justify-start">
            <div
              role="status"
              className="flex items-center gap-2 rounded-2xl bg-muted px-4 py-2.5 text-sm text-muted-foreground"
            >
              {t("Thinking")}
              <span className="flex gap-1" aria-hidden="true">
                {[0, 150, 300].map((delay) => (
                  <span
                    key={delay}
                    style={{ animationDelay: `${delay}ms` }}
                    className="size-1.5 animate-bounce rounded-full bg-current motion-reduce:animate-none"
                  />
                ))}
              </span>
            </div>
          </div>
        )}

        {error && (
          <p data-testid="chat-error" className="rounded-xl border border-amber-300/60 bg-amber-50/60 px-3 py-2 text-xs text-amber-900 dark:border-amber-800/60 dark:bg-amber-950/30 dark:text-amber-200/90">
            {error}
          </p>
        )}

        {!sending && !error && answer && (
          <div className="space-y-2 text-xs text-muted-foreground">
            {answer.sources.length > 0 && (
              <div data-testid="chat-sources">
                <p className="font-medium">{t("Sources")}</p>
                <ul className="mt-1 space-y-0.5">
                  {answer.sources.map((s) => (
                    <li key={s.document_id}>
                      <Link href={`/patients/${patientId}/documents/${s.document_id}`} className="underline underline-offset-2 hover:text-primary">
                        {s.file_name}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            )}
            <p data-testid="chat-disclaimer">{answer.disclaimer}</p>
            {notice}
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); send(input.trim()); }}
        className="flex gap-2 border-t px-3 pt-3"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={t("Placeholder")}
          aria-label={t("Placeholder")}
          className="flex-1 rounded-lg border bg-background px-3 py-2 text-sm outline-none focus:ring-2 focus:ring-primary"
        />
        <button
          type="submit"
          disabled={sending || !input.trim()}
          aria-label={t("Send")}
          className="rounded-lg bg-primary px-3 py-2 text-primary-foreground transition-colors hover:bg-primary/90 disabled:opacity-50"
        >
          <Send className="size-4" />
        </button>
      </form>
      <p className="px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-1.5 text-center text-xs text-muted-foreground">{t("Notice")}</p>
    </div>
  );
}

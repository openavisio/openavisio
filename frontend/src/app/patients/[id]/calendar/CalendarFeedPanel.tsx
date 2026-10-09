"use client";

import { useEffect, useState, useTransition } from "react";
import { CalendarClock, Copy, Check, Trash2, Plus, AlertTriangle } from "lucide-react";
import { useTranslations, useFormatter } from "next-intl";
import {
  type CalendarFeed,
  createCalendarFeedAction,
  listCalendarFeedsAction,
  revokeCalendarFeedAction,
} from "./feed-actions";

export function CalendarFeedPanel({ patientId }: { patientId: string }) {
  const t = useTranslations("CalendarFeed");
  const f = useFormatter();
  const [feeds, setFeeds] = useState<CalendarFeed[]>([]);
  const [freshUrl, setFreshUrl] = useState("");
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState("");
  const [pending, startTransition] = useTransition();

  useEffect(() => {
    listCalendarFeedsAction(patientId).then(setFeeds);
  }, [patientId]);

  function create() {
    setError("");
    startTransition(async () => {
      const res = await createCalendarFeedAction(patientId);
      if (res.error) return setError(res.error);
      setFreshUrl(res.url ?? "");
      setFeeds(await listCalendarFeedsAction(patientId));
    });
  }

  function revoke(feedId: string) {
    setError("");
    startTransition(async () => {
      const res = await revokeCalendarFeedAction(patientId, feedId);
      if (res.error) return setError(res.error);
      setFreshUrl("");
      setFeeds(await listCalendarFeedsAction(patientId));
    });
  }

  return (
    <section className="rounded-lg border bg-card p-4">
      <h2 className="flex items-center gap-2 font-medium">
        <CalendarClock className="size-4" aria-hidden="true" />
        {t("title")}
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">{t("intro")}</p>

      {/* The whole point of the disclosure: appointments leave the deployment. */}
      <p className="mt-3 flex gap-2 rounded-md bg-amber-50 p-3 text-sm text-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
        <span>{t("privacyWarning")}</span>
      </p>
      <p className="mt-2 text-xs text-muted-foreground">{t("windowHint")}</p>

      {freshUrl && (
        <div className="mt-3 rounded-md border border-dashed p-3">
          <p className="text-sm font-medium">{t("shownOnce")}</p>
          <div className="mt-2 flex items-center gap-2">
            <code className="min-w-0 flex-1 truncate rounded bg-muted px-2 py-1 text-xs">{freshUrl}</code>
            <button
              type="button"
              className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-accent"
              onClick={() => {
                navigator.clipboard.writeText(freshUrl);
                setCopied(true);
                setTimeout(() => setCopied(false), 2000);
              }}
            >
              {copied ? <Check className="size-3" aria-hidden="true" /> : <Copy className="size-3" aria-hidden="true" />}
              {copied ? t("copied") : t("copy")}
            </button>
          </div>
        </div>
      )}

      {feeds.length > 0 && (
        <ul className="mt-3 divide-y rounded-md border">
          {feeds.map((feed) => (
            <li key={feed.id} className="flex items-center justify-between gap-3 px-3 py-2 text-sm">
              <span className="min-w-0">
                <span className="block truncate">
                  {t("createdAt", { date: f.dateTime(new Date(feed.created_at), { dateStyle: "medium" }) })}
                </span>
                <span className="block text-xs text-muted-foreground">
                  {feed.last_accessed_at
                    ? t("lastAccessed", {
                        date: f.dateTime(new Date(feed.last_accessed_at), { dateStyle: "medium", timeStyle: "short" }),
                      })
                    : t("neverAccessed")}
                </span>
              </span>
              <button
                type="button"
                disabled={pending}
                className="flex items-center gap-1 rounded-md border px-2 py-1 text-xs hover:bg-accent disabled:opacity-50"
                onClick={() => revoke(feed.id)}
              >
                <Trash2 className="size-3" aria-hidden="true" />
                {t("revoke")}
              </button>
            </li>
          ))}
        </ul>
      )}

      {error && <p className="mt-2 text-sm text-destructive">{error}</p>}

      <button
        type="button"
        disabled={pending}
        className="mt-3 flex items-center gap-1 rounded-md border px-3 py-1.5 text-sm hover:bg-accent disabled:opacity-50"
        onClick={create}
      >
        <Plus className="size-4" aria-hidden="true" />
        {t("create")}
      </button>
    </section>
  );
}

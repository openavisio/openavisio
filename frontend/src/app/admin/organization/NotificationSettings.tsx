"use client";

import { useState, useTransition } from "react";
import { useTranslations } from "next-intl";
import { updateNotificationSettings } from "@/lib/api";

type Settings = {
  event_reminder: boolean;
  caregiver_added: boolean;
  invitation: boolean;
  include_content: boolean;
  document_processed: boolean;
};

// label/description are message keys in the Org namespace, not text.
const LABELS: { key: keyof Settings; label: string; description: string }[] = [
  { key: "event_reminder", label: "NotifyEventReminder", description: "NotifyEventReminderHint" },
  { key: "caregiver_added", label: "NotifyCaregiverAdded", description: "NotifyCaregiverAddedHint" },
  { key: "invitation", label: "NotifyInvitation", description: "NotifyInvitationHint" },
  { key: "document_processed", label: "NotifyDocumentProcessed", description: "NotifyDocumentProcessedHint" },
  { key: "include_content", label: "NotifyIncludeContent", description: "NotifyIncludeContentHint" },
];

export function NotificationSettings({ initial }: { initial: Settings }) {
  const t = useTranslations("Org");
  const [settings, setSettings] = useState(initial);
  const [pending, startTransition] = useTransition();
  const [saved, setSaved] = useState(false);
  const [failed, setFailed] = useState(false);

  function toggle(key: keyof Settings) {
    const next = { ...settings, [key]: !settings[key] };
    setSettings(next);
    setSaved(false);
    setFailed(false);
    startTransition(async () => {
      try {
        await updateNotificationSettings({ [key]: next[key] });
        setSaved(true);
        setTimeout(() => setSaved(false), 2000);
      } catch {
        setSettings(settings);
        setFailed(true);
      }
    });
  }

  return (
    <div className="rounded-xl border bg-card p-6 space-y-4">
      <div>
        <h2 className="font-medium text-sm">{t("NotifyTitle")}</h2>
        <p className="text-xs text-muted-foreground mt-0.5">{t("NotifyHint")}</p>
      </div>

      <div className="space-y-3">
        {LABELS.map(({ key, label, description }) => (
          <div key={key} className="flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-medium">{t(label)}</div>
              <div className="text-xs text-muted-foreground">{t(description)}</div>
            </div>
            <button
              type="button"
              role="switch"
              aria-checked={settings[key]}
              onClick={() => toggle(key)}
              disabled={pending}
              className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors disabled:opacity-50 ${
                settings[key] ? "bg-primary" : "bg-muted"
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 rounded-full bg-white shadow transition-transform ${
                  settings[key] ? "translate-x-4" : "translate-x-1"
                }`}
              />
            </button>
          </div>
        ))}
      </div>

      {saved && <p className="text-xs text-green-600">{t("Saved")}</p>}
      {failed && <p className="text-xs text-destructive">{t("SaveFailed")}</p>}
    </div>
  );
}

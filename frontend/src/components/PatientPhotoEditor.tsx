"use client";

import { useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Camera, Trash2, Loader2 } from "lucide-react";
import { PatientAvatar } from "./PatientAvatar";

// Avatar + small corner badges to set/replace/remove the patient photo. Badges
// sit on the rim so they never cover the image, and are always visible (no
// hover dependency, so they work on touch too). Photo stays encrypted under the
// patient KEK; this only drives the UI.
export function PatientPhotoEditor({
  patientId,
  givenName,
  familyName,
  hasPhoto,
  labels,
}: {
  patientId: string;
  givenName?: string;
  familyName?: string;
  hasPhoto: boolean;
  labels: { change: string; remove: string; failed: string };
}) {
  const router = useRouter();
  const inputRef = useRef<HTMLInputElement>(null);
  const [busy, setBusy] = useState(false);
  const photoUrl = hasPhoto ? `/api/patients/${patientId}/photo` : null;

  async function upload(file: File) {
    setBusy(true);
    const fd = new FormData();
    fd.append("file", file);
    const res = await fetch(`/api/patients/${patientId}/photo`, { method: "POST", body: fd });
    setBusy(false);
    if (!res.ok) {
      alert(labels.failed);
      return;
    }
    router.refresh();
  }

  async function remove() {
    setBusy(true);
    await fetch(`/api/patients/${patientId}/photo`, { method: "DELETE" });
    setBusy(false);
    router.refresh();
  }

  return (
    <div className="flex flex-col items-center gap-2">
      <PatientAvatar givenName={givenName} familyName={familyName} photoUrl={photoUrl} />

      <input
        ref={inputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) upload(f);
          e.target.value = "";
        }}
      />

      {/* controls sit below the avatar — never over the photo */}
      <div className="flex items-center gap-1">
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={busy}
          title={labels.change}
          aria-label={labels.change}
          className="flex size-11 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-accent hover:text-foreground disabled:opacity-70"
        >
          {busy ? <Loader2 className="size-6 animate-spin" /> : <Camera className="size-6" />}
        </button>
        {hasPhoto && !busy && (
          <button
            type="button"
            onClick={remove}
            title={labels.remove}
            aria-label={labels.remove}
            className="flex size-11 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-destructive/10 hover:text-destructive"
          >
            <Trash2 className="size-5" />
          </button>
        )}
      </div>
    </div>
  );
}

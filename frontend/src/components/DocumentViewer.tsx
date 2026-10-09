"use client";

import { useEffect, useState } from "react";
import { Maximize2 } from "lucide-react";

interface Props {
  docId: string;
  contentType: string;
  className?: string;
}

export function DocumentViewer({ docId, contentType, className = "" }: Props) {
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    let url: string | null = null;
    fetch(`/api/documents/${docId}/file`)
      .then((res) => {
        if (!res.ok) throw new Error();
        return res.blob();
      })
      .then((blob) => {
        url = URL.createObjectURL(blob);
        setBlobUrl(url);
      })
      .catch(() => setError(true));
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [docId]);

  if (error) {
    return (
      <div className={`flex items-center justify-center bg-muted rounded-xl text-sm text-muted-foreground ${className}`}>
        Could not load document.
      </div>
    );
  }

  if (!blobUrl) {
    return (
      <div className={`flex items-center justify-center bg-muted rounded-xl text-sm text-muted-foreground animate-pulse ${className}`}>
        Loading…
      </div>
    );
  }

  if (contentType.startsWith("image/")) {
    return (
      <div className={`flex items-center justify-center bg-muted rounded-xl overflow-hidden ${className}`}>
        <img src={blobUrl} alt="Document" className="max-w-full max-h-full object-contain" />
      </div>
    );
  }

  return (
    <div className={`relative ${className}`}>
      <iframe
        src={blobUrl}
        className="block h-full w-full rounded-xl border bg-white"
        title="Document"
      />
      {/* the native viewer cramped into half a column zooms badly — the new tab
          gives it the whole window and working pan/zoom */}
      <button
        type="button"
        onClick={() => window.open(blobUrl, "_blank")}
        title="Open full size"
        aria-label="Open full size"
        className="absolute right-3 top-3 rounded-md border bg-card/90 p-1.5 text-muted-foreground shadow-sm backdrop-blur hover:text-foreground"
      >
        <Maximize2 className="h-4 w-4" />
      </button>
    </div>
  );
}

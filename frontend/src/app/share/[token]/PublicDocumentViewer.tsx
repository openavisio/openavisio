"use client";

import { useEffect, useState } from "react";
import { Download } from "lucide-react";
import { useTranslations } from "next-intl";

interface Props {
  token: string;
  docId?: string;
  src?: string;
  contentType: string;
  fileName: string;
}

export function PublicDocumentViewer({ token, docId, src, contentType, fileName }: Props) {
  const t = useTranslations("PublicShare");
  const [blobUrl, setBlobUrl] = useState<string | null>(null);
  const [error, setError] = useState(false);

  const base = src ?? `/api/public/document-shares/${encodeURIComponent(token)}/documents/${docId}/file`;

  useEffect(() => {
    let url: string | null = null;
    fetch(base)
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
  }, [base]);

  return (
    <div className="space-y-2">
      {error ? (
        <div className="flex items-center justify-center bg-muted rounded-xl text-sm text-muted-foreground h-[60vh]">
          {t("couldNotLoad")}
        </div>
      ) : !blobUrl ? (
        <div className="flex items-center justify-center bg-muted rounded-xl text-sm text-muted-foreground animate-pulse h-[60vh]">
          {t("loading")}
        </div>
      ) : contentType.startsWith("image/") ? (
        <div className="flex items-center justify-center bg-muted rounded-xl overflow-hidden h-[60vh]">
          <img src={blobUrl} alt={fileName} className="max-w-full max-h-full object-contain" />
        </div>
      ) : (
        <iframe src={blobUrl} className="block w-full h-[60vh] rounded-xl border bg-white" title={fileName} />
      )}

      <a
        href={`${base}?download=true`}
        className="inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm font-medium hover:bg-muted"
      >
        <Download className="size-4" />
        {t("download")}
      </a>
    </div>
  );
}

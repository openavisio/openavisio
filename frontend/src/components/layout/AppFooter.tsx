import Link from "next/link";
import { Heart } from "lucide-react";
import { useTranslations } from "next-intl";

// Every page needs a route to the Impressum (§5 DDG) and the privacy policy —
// a link buried in the login screen does not count. This is also the honest place
// to say who runs the instance and under what licence the software is used.
export function AppFooter({ orgName }: { orgName?: string }) {
  const t = useTranslations("Footer");
  return (
    <footer className="mt-auto shrink-0 border-t px-4 py-4 pb-[calc(1rem+env(safe-area-inset-bottom))] text-xs text-muted-foreground lg:pb-4">
      <div className="mx-auto flex max-w-[1200px] flex-col items-center justify-between gap-2 sm:flex-row">
        <div className="flex flex-wrap items-center justify-center gap-x-3 gap-y-1">
          <Link href="/imprint" className="hover:text-foreground hover:underline">Impressum</Link>
          <span aria-hidden>·</span>
          <Link href="/privacy" className="hover:text-foreground hover:underline">Datenschutz</Link>
          <span aria-hidden>·</span>
          {/* AGPL-3.0 §13: anyone who USES this over a network may demand the
              source. Both repositories are private today, so this points at the
              project site — the moment outside users get access (the dup15q
              Verein, a pilot), a real source link becomes an obligation, not a
              nicety. See the note in README. */}
          <a
            href="https://openavisio.org"
            target="_blank"
            rel="noreferrer"
            className="hover:text-foreground hover:underline"
          >
            OpenAvisio (AGPL-3.0)
          </a>
        </div>

        <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1">
          {orgName && (
            <>
              <span>{t("RunBy", { org: orgName })}</span>
              <span aria-hidden>·</span>
            </>
          )}
          <span className="inline-flex items-center gap-1">
            {t.rich("BuiltWith", {
              heart: () => <Heart className="size-3 fill-rose-500 text-rose-500" aria-label={t("Love")} />,
            })}
          </span>
        </div>
      </div>
    </footer>
  );
}

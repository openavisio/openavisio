import Link from "next/link";
import { ChevronRight } from "lucide-react";

type Crumb = { label: string; href: string };

export function Breadcrumb({
  crumbs,
  current,
  className = "mb-6",
}: {
  crumbs: Crumb[];
  current: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex items-center gap-1.5 flex-wrap ${className}`}>
      {crumbs.map((c) => (
        <span key={c.href} className="flex items-center gap-1.5">
          <Link
            href={c.href}
            className="text-xl font-semibold text-muted-foreground hover:text-foreground transition-colors"
          >
            {c.label}
          </Link>
          <ChevronRight className="size-4 text-muted-foreground/60 shrink-0" />
        </span>
      ))}
      <h1 className="text-xl font-bold">{current}</h1>
    </div>
  );
}

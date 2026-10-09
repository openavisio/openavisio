import { AppLayout } from "@/components/layout/AppLayout";
import { getHandout } from "@/lib/api";
import { getTranslations } from "next-intl/server";
import { Breadcrumb } from "@/components/Breadcrumb";
import { AlertCircle } from "lucide-react";
import { HandoutPreview } from "./HandoutPreview";
import { VARIANTS } from "@/lib/handout";
import Link from "next/link";

export default async function HandoutPage({ params, searchParams }: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ v?: string }>;
}) {
  const { id } = await params;
  const { v } = await searchParams;
  const variant = VARIANTS.find((x) => x === v) ?? "doctors";
  const t = await getTranslations("Handout");
  const handout = await getHandout(id, variant).catch(() => null);

  const crumb = (
    <Breadcrumb
      crumbs={handout ? [{ label: handout.patient.name, href: `/patients/${id}` }] : []}
      current={t(`title.${variant}`)}
      className=""
    />
  );

  return (
    <AppLayout>
      <nav className="mb-4 flex flex-wrap gap-2">
        {VARIANTS.map((x) => (
          <Link key={x} href={`/patients/${id}/handout?v=${x}`} aria-current={x === variant ? "page" : undefined}
            className={`rounded-full border px-3 py-1 text-sm ${x === variant ? "bg-primary text-primary-foreground" : "hover:bg-accent"}`}>
            {t(`title.${x}`)}
          </Link>
        ))}
      </nav>
      {handout ? (
        <HandoutPreview key={variant} patientId={id} handout={handout}>{crumb}</HandoutPreview>
      ) : (
        <>
          <div className="mb-6">{crumb}</div>
          <div className="flex items-center gap-2 rounded-lg bg-destructive/10 text-destructive px-4 py-3 text-sm">
            <AlertCircle className="size-4 shrink-0" />
            {t("LoadError")}
          </div>
        </>
      )}
    </AppLayout>
  );
}

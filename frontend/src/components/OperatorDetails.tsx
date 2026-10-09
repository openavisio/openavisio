import Link from "next/link";
import { AlertTriangle } from "lucide-react";

export interface Operator {
  legal_name?: string | null;
  legal_street?: string | null;
  legal_postcode?: string | null;
  legal_city?: string | null;
  legal_country?: string | null;
  legal_email?: string | null;
  legal_phone?: string | null;
  legal_responsible?: string | null;
  legal_vat_id?: string | null;
  legal_register?: string | null;
  dpo_contact?: string | null;
}

export function hasOperatorDetails(o: Operator | null | undefined): boolean {
  return !!(o?.legal_name && o?.legal_street && o?.legal_city && o?.legal_email);
}

/** The operator's details, or an honest gap.
 *
 * The pages used to print `[ORGANISATIONS-NAME]` in production — a placeholder
 * that looks like a legal notice and is not one (#112). If the operator has not
 * filled these in, say so and point the admin at the setting; never invent them,
 * and never let a template pass for an Impressum.
 */
export function OperatorDetails({ operator, missingLabel, missingCta }: {
  operator: Operator | null | undefined;
  missingLabel: string;
  missingCta: string;
}) {
  if (!hasOperatorDetails(operator)) {
    return (
      <div className="flex items-start gap-2 rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-800 dark:bg-amber-950 dark:text-amber-200">
        <AlertTriangle className="mt-0.5 size-4 shrink-0" />
        <div>
          <p>{missingLabel}</p>
          <Link href="/admin/organization" className="mt-1 inline-block font-medium underline">
            {missingCta}
          </Link>
        </div>
      </div>
    );
  }

  const o = operator!;
  return (
    <address className="rounded-lg border bg-muted/50 px-4 py-3 text-sm not-italic leading-relaxed">
      {o.legal_name}
      <br />
      {o.legal_street}
      <br />
      {o.legal_postcode} {o.legal_city}
      {o.legal_country && (
        <>
          <br />
          {o.legal_country}
        </>
      )}
      <br />
      <a href={`mailto:${o.legal_email}`} className="underline">{o.legal_email}</a>
      {o.legal_phone && (
        <>
          <br />
          {o.legal_phone}
        </>
      )}
    </address>
  );
}

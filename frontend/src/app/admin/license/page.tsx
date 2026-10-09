import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { LicenseForm } from "./LicenseForm";

const API = process.env.API_URL || "http://localhost:8000";

export const dynamic = "force-dynamic";

const THIRD_PARTY = [
  { name: "Next.js", license: "MIT", url: "https://github.com/vercel/next.js" },
  { name: "React", license: "MIT", url: "https://github.com/facebook/react" },
  { name: "Auth.js (next-auth)", license: "ISC", url: "https://github.com/nextauthjs/next-auth" },
  { name: "next-intl", license: "MIT", url: "https://github.com/amannn/next-intl" },
  { name: "Tailwind CSS", license: "MIT", url: "https://github.com/tailwindlabs/tailwindcss" },
  { name: "shadcn/ui", license: "MIT", url: "https://github.com/shadcn-ui/ui" },
  { name: "Lucide Icons", license: "ISC", url: "https://github.com/lucide-icons/lucide" },
  { name: "FastAPI", license: "MIT", url: "https://github.com/tiangolo/fastapi" },
  { name: "SQLAlchemy", license: "MIT", url: "https://github.com/sqlalchemy/sqlalchemy" },
  { name: "Alembic", license: "MIT", url: "https://github.com/sqlalchemy/alembic" },
  { name: "Celery", license: "BSD-3-Clause", url: "https://github.com/celery/celery" },
  { name: "pgvector", license: "PostgreSQL", url: "https://github.com/pgvector/pgvector" },
  { name: "Caddy", license: "Apache-2.0", url: "https://github.com/caddyserver/caddy" },
];

export default async function LicensePage() {
  const session = await auth();
  const accessToken = (session as any)?.accessToken;

  let licenseInfo = {
    tier: "personal",
    has_license: false,
    is_grace_period: false,
    issued_to: null as string | null,
    expires_at: null as string | null,
    grace_ends_at: null as string | null,
  };

  if (accessToken) {
    try {
      const res = await fetch(`${API}/api/admin/license`, {
        headers: { Authorization: `Bearer ${accessToken}` },
        cache: "no-store",
      });
      if (res.ok) {
        licenseInfo = await res.json();
      }
    } catch {
      // fall through to default personal tier display
    }
  }

  return (
    <AppLayout>
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">License</h1>
        <p className="text-sm text-muted-foreground mt-1">
          Entitlement tier and open-source license information.
        </p>
      </div>

      <LicenseForm initialInfo={licenseInfo} />

      <div className="rounded-xl border bg-card p-6 space-y-3">
        <h2 className="font-medium text-sm">OpenAvisio</h2>
        <p className="text-sm text-muted-foreground leading-relaxed">
          Copyright © 2024–2026 OpenAvisio Contributors. This program is free software: you can
          redistribute it and/or modify it under the terms of the GNU Affero General Public License
          as published by the Free Software Foundation, either version 3 of the License, or (at
          your option) any later version.
        </p>
        <p className="text-sm text-muted-foreground leading-relaxed">
          This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
          without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
          See the GNU Affero General Public License for more details.
        </p>
      </div>

      <div className="rounded-xl border bg-card overflow-hidden">
        <div className="px-4 py-3 border-b bg-muted/50 font-medium text-sm">
          Third-party Open Source Components
        </div>
        <table className="w-full text-sm">
          <thead className="border-b bg-muted/30">
            <tr>
              <th className="px-4 py-2 text-left font-medium text-xs">Component</th>
              <th className="px-4 py-2 text-left font-medium text-xs">License</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {THIRD_PARTY.map((l) => (
              <tr key={l.name} className="hover:bg-muted/30">
                <td className="px-4 py-2">
                  <a
                    href={l.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="hover:underline text-primary"
                  >
                    {l.name}
                  </a>
                </td>
                <td className="px-4 py-2 text-xs text-muted-foreground font-mono">{l.license}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </AppLayout>
  );
}

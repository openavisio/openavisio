import { AppLayout } from "@/components/layout/AppLayout";
import { auth } from "@/auth";
import { AcceptButton } from "./AcceptButton";
import { Users } from "lucide-react";
import { getTranslations } from "next-intl/server";

const API = process.env.API_URL || "http://localhost:8000";

async function getInviteInfo(token: string, accessToken: string) {
  const res = await fetch(`${API}/api/groups/invite/info?token=${encodeURIComponent(token)}`, {
    headers: { Authorization: `Bearer ${accessToken}` },
    cache: "no-store",
  });
  if (!res.ok) return null;
  return res.json();
}

export default async function AcceptInvitePage({
  searchParams,
}: {
  searchParams: Promise<{ token?: string }>;
}) {
  const { token } = await searchParams;
  const session = await auth();
  const accessToken = (session as any)?.accessToken as string | undefined;
  const t = await getTranslations("GroupPage");
  const ta = await getTranslations("Access");

  if (!token) {
    return (
      <AppLayout>
        <div className="max-w-md mx-auto mt-16 text-center space-y-2">
          <p className="text-muted-foreground">{ta("InviteNoToken")}</p>
        </div>
      </AppLayout>
    );
  }

  const info = accessToken ? await getInviteInfo(token, accessToken) : null;

  return (
    <AppLayout>
      <div className="max-w-md mx-auto mt-16">
        <div className="rounded-xl border bg-card p-8 text-center space-y-6">
          <div className="flex justify-center">
            <div className="rounded-full bg-primary/10 p-4">
              <Users className="size-8 text-primary" />
            </div>
          </div>

          {info ? (
            <>
              <div className="space-y-1">
                <p className="text-muted-foreground text-sm">{t("InvitedToJoin")}</p>
                <h1 className="text-2xl font-bold">{info.group_name}</h1>
              </div>
              <AcceptButton inviteToken={token} />
            </>
          ) : (
            <div className="space-y-2">
              <h1 className="text-xl font-bold">{ta("InviteInvalidTitle")}</h1>
              <p className="text-muted-foreground text-sm">
                {ta("InviteInvalidBody")}
              </p>
            </div>
          )}
        </div>
      </div>
    </AppLayout>
  );
}

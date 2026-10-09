import { Suspense } from "react";
import { AiNotice } from "@/components/AiNotice";
import { ChatOverlay } from "./ChatOverlay";

/** The chat rides along on every patient screen instead of being a section of
 *  its own (#201). AiNotice is an async server component and is rendered *here*,
 *  passed down as a prop — rendering it from inside the client overlay is what
 *  killed the old chat page (a0e7cff). */
export default async function PatientLayout({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <>
      {children}
      <Suspense>
        <ChatOverlay patientId={id} notice={<AiNotice />} />
      </Suspense>
    </>
  );
}

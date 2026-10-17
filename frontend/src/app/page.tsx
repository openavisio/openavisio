import { redirect } from "next/navigation";
import { getPatients } from "@/lib/api";

// #327: the landing after sign-in opens the only Patient. Only here: /patients stays
// the list, or a second one could never be created (ADR 046).
export default async function Home() {
  const patients = await getPatients().catch(() => []);
  redirect(patients.length === 1 ? `/patients/${patients[0].id}` : "/patients");
}

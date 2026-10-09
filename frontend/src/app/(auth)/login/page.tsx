import { Suspense } from "react";
import { LoginForm } from "./LoginForm";

// Server component only to read DEMO_MODE: it is a runtime env var (same as the
// upload dropzone reads), not a NEXT_PUBLIC build arg (ADR 010).
export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm demoMode={process.env.DEMO_MODE === "true"} />
    </Suspense>
  );
}

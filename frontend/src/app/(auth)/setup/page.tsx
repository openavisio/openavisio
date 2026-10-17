import { SetupWizard } from "./SetupWizard";

// Server component only to read HOSTED_SETUP at runtime, like DEMO_MODE on the login page.
export default function SetupPage() {
  return <SetupWizard hosted={process.env.HOSTED_SETUP === "true"} />;
}

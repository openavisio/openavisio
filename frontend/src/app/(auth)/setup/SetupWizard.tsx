"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { useWizardState } from "./_hooks/useWizardState";
import { WizardShell } from "./_components/WizardShell";
import { Step1Language } from "./_steps/Step1Language";
import { Step2Organization } from "./_steps/Step2Organization";
import { Step4SMTP } from "./_steps/Step4SMTP";
import { Step5Admin } from "./_steps/Step5Admin";
import { Step6Patient } from "./_steps/Step6Patient";
import { Step7Done } from "./_steps/Step7Done";

// hosted: the customer is a family with a link (ADR 0010). No language, organisation or mail
// server to choose; they land on e-mail and password.
export function SetupWizard({ hosted }: { hosted: boolean }) {
  const t = useTranslations("Setup");
  const { state, dispatch } = useWizardState(hosted);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  // Kept in component state (not the sessionStorage-persisted wizard) so the
  // one-time setup token is never written to disk.
  // The welcome mail links to /setup#token=… (#264). A fragment never reaches
  // the server, so no access log or Referer sees it; read it here, then drop it
  // from the address bar. The field stays editable either way.
  const [bootstrapToken, setBootstrapToken] = useState(() =>
    typeof window === "undefined" ? "" : new URLSearchParams(location.hash.slice(1)).get("token") ?? "",
  );
  useEffect(() => {
    if (new URLSearchParams(location.hash.slice(1)).has("token")) {
      history.replaceState(history.state, "", location.pathname + location.search);
    }
  }, []);
  // Same reasoning as the bootstrap token: the recovery code exists in this one
  // response and must not be written to sessionStorage (ADR 044).
  const [recoveryCode, setRecoveryCode] = useState("");

  function next() {
    // Step 1: require locale selection
    if (state.step === 0 && !state.locale) return;
    // Step 2: an organisation needs a name. A household is never asked (ADR 046).
    if (state.step === 1 && !state.org.isHousehold && !state.org.name.trim()) return;
    // Step 4: require email + password + bootstrap token
    if (state.step === 3 && (!state.admin.email || !state.admin.password || !bootstrapToken)) return;
    setError("");
    dispatch({ type: "SET_STEP", step: state.step + 1 });
  }

  function back() {
    setError("");
    dispatch({ type: "SET_STEP", step: state.step - 1 });
  }

  async function submit() {
    setSubmitting(true);
    setError("");

    const body: Record<string, unknown> = {
      name: state.org.isHousehold ? t("HouseholdName") : state.org.name,
      description: state.org.isHousehold ? undefined : state.org.description || undefined,
      is_household: state.org.isHousehold,
      locale: state.locale || "en",
      admin_email: state.admin.email,
      admin_password: state.admin.password,
      admin_first_name: state.admin.firstName || undefined,
      admin_last_name: state.admin.lastName || undefined,
    };

    if (!state.smtp.skip && state.smtp.host) {
      body.smtp = {
        host: state.smtp.host,
        port: parseInt(state.smtp.port) || 587,
        user: state.smtp.user || undefined,
        password: state.smtp.password || undefined,
        from_address: state.smtp.from || undefined,
      };
    }

    if (!state.patient.skip && state.patient.givenName && state.patient.familyName) {
      body.first_patient = {
        given_name: state.patient.givenName,
        family_name: state.patient.familyName,
        birth_date: state.patient.birthDate || undefined,
      };
    }

    const res = await fetch("/api/backend/organization/init", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-Bootstrap-Token": bootstrapToken },
      body: JSON.stringify(body),
    });

    setSubmitting(false);

    if (res.ok) {
      const data = await res.json().catch(() => ({}));
      setRecoveryCode(data.recovery_code || "");
      dispatch({ type: "SET_STEP", step: 5 });
    } else {
      const data = await res.json().catch(() => ({}));
      setError(data.detail || "Setup failed");
    }
  }

  const steps = [
    <Step1Language key="1" state={state} onLocale={(locale) => dispatch({ type: "SET_LOCALE", locale })} />,
    <Step2Organization key="2" state={state} onChange={(org) => dispatch({ type: "UPDATE_ORG", org })} />,
    <Step4SMTP
      key="4"
      state={state}
      onChange={(smtp) => dispatch({ type: "UPDATE_SMTP", smtp })}
      onSkip={() => dispatch({ type: "UPDATE_SMTP", smtp: { skip: true } })}
    />,
    <Step5Admin
      key="5"
      state={state}
      onChange={(admin) => dispatch({ type: "UPDATE_ADMIN", admin })}
      bootstrapToken={bootstrapToken}
      onBootstrapToken={setBootstrapToken}
      hosted={hosted}
    />,
    <Step6Patient
      key="6"
      state={state}
      onChange={(patient) => dispatch({ type: "UPDATE_PATIENT", patient })}
      onSkip={() => dispatch({ type: "UPDATE_PATIENT", patient: { skip: true } })}
    />,
    <Step7Done key="7" recoveryCode={recoveryCode} hosted={hosted} />,
  ];

  return (
    <WizardShell
      state={state}
      onNext={next}
      onBack={back}
      onSubmit={submit}
      submitting={submitting}
      error={error}
      hosted={hosted}
    >
      {steps[state.step]}
    </WizardShell>
  );
}

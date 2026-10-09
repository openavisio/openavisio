"use client";

import { useReducer, useEffect } from "react";

export interface WizardState {
  step: number;
  locale: string;
  org: { name: string; description: string; isHousehold: boolean };
  smtp: { host: string; port: string; user: string; password: string; from: string; skip: boolean };
  admin: { email: string; password: string; firstName: string; lastName: string };
  patient: { givenName: string; familyName: string; birthDate: string; skip: boolean };
}

const INITIAL: WizardState = {
  step: 0,
  locale: "en",
  org: { name: "OpenAvisio", description: "", isHousehold: true },  // ADR 046
  smtp: { host: "", port: "587", user: "", password: "", from: "", skip: false },
  admin: { email: "", password: "", firstName: "", lastName: "" },
  patient: { givenName: "", familyName: "", birthDate: "", skip: false },
};

type Action =
  | { type: "SET_STEP"; step: number }
  | { type: "SET_LOCALE"; locale: string }
  | { type: "UPDATE_ORG"; org: Partial<WizardState["org"]> }
  | { type: "UPDATE_SMTP"; smtp: Partial<WizardState["smtp"]> }
  | { type: "UPDATE_ADMIN"; admin: Partial<WizardState["admin"]> }
  | { type: "UPDATE_PATIENT"; patient: Partial<WizardState["patient"]> };

function reducer(state: WizardState, action: Action): WizardState {
  switch (action.type) {
    case "SET_STEP": return { ...state, step: action.step };
    case "SET_LOCALE": return { ...state, locale: action.locale };
    case "UPDATE_ORG": return { ...state, org: { ...state.org, ...action.org } };
    case "UPDATE_SMTP": return { ...state, smtp: { ...state.smtp, ...action.smtp } };
    case "UPDATE_ADMIN": return { ...state, admin: { ...state.admin, ...action.admin } };
    case "UPDATE_PATIENT": return { ...state, patient: { ...state.patient, ...action.patient } };
  }
}

const SESSION_KEY = "openavisio_setup_wizard";

export function useWizardState() {
  const [state, dispatch] = useReducer(reducer, INITIAL, (initial) => {
    if (typeof window === "undefined") return initial;
    try {
      const stored = sessionStorage.getItem(SESSION_KEY);
      return stored ? { ...initial, ...JSON.parse(stored) } : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    sessionStorage.setItem(SESSION_KEY, JSON.stringify(state));
  }, [state]);

  return { state, dispatch };
}

"use server";

import { auth } from "@/auth";
import type { Einstufung, EinstufungInput, Scale } from "@/lib/einstufung";
import type { EmergencyPlan, EmergencyPlanInput } from "@/lib/emergencyPlan";
import type { CareNotes } from "@/lib/careNotes";
import type { CarerUpdate, CarerUpdateInput } from "@/lib/carerUpdates";
import type { Handout } from "@/lib/handout";
import type { Aging, HistoryFact, IntakeForm, IntakeFormDetail } from "@/lib/intake";

const API_URL = process.env.API_URL || "http://localhost:8000";

async function getToken(): Promise<string | null> {
  const session = await auth();
  return (session as any)?.accessToken ?? null;
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const token = await getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  // Never cache: everything here is live, per-user data. A cached response once
  // froze the admin AI-backend status on "Disconnected" long after it recovered.
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", ...options, headers });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Like request() but returns the raw body as text — for CSV and other non-JSON downloads.
async function requestText(path: string): Promise<string> {
  const token = await getToken();
  const headers: Record<string, string> = {};
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { cache: "no-store", headers });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.text();
}

async function requestBase64(path: string, body: unknown): Promise<string> {
  const token = await getToken();
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(`${API_URL}${path}`, { method: "POST", cache: "no-store", headers, body: JSON.stringify(body) });
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return Buffer.from(await res.arrayBuffer()).toString("base64");
}

const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body ? JSON.stringify(body) : undefined }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};

// Patient
export const getPatients = async (q?: string) => api.get<any[]>(`/api/patients${q ? `?q=${q}` : ""}`);
export const getFavoritePatients = async () => api.get<any[]>(`/api/patients/favorites`);
export const addFavorite = async (id: string) => api.put<void>(`/api/patients/${id}/favorite`);
export const removeFavorite = async (id: string) => api.delete<void>(`/api/patients/${id}/favorite`);
export const getPatient = async (id: string) => api.get<any>(`/api/patients/${id}`);
export const createPatient = async (data: any) => api.post<any>("/api/patients", data);
export const updatePatient = async (id: string, data: any) => api.put<any>(`/api/patients/${id}`, data);
export const deletePatient = async (id: string) => api.delete<void>(`/api/patients/${id}`);

// Dashboard
export const getDashboard = async (patientId: string) => api.get<any>(`/api/patients/${patientId}/dashboard`);

// Observations
export const getObservations = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<any[]>(`/api/patients/${patientId}/observations${q}`);
};
export const createObservation = async (patientId: string, data: any) => api.post<any>(`/api/patients/${patientId}/observations`, data);
export const deleteObservation = async (id: string) => api.delete<void>(`/api/observations/${id}`);

// Documents
export const getDocuments = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<any[]>(`/api/patients/${patientId}/documents${q}`);
};
export const getDocument = async (id: string) => api.get<any>(`/api/documents/${id}`);
export const getDocumentDetail = async (id: string) => api.get<any>(`/api/documents/${id}/detail`);
export const verifyDocument = async (id: string, data: any) => api.post<any>(`/api/documents/${id}/verify`, data);
export const updateDocument = async (id: string, data: { issued_date?: string | null; description?: string | null; type?: string | null; correspondent_id?: string | null }) => api.patch<any>(`/api/documents/${id}`, data);
export const deleteDocument = async (id: string) => api.delete<void>(`/api/documents/${id}`);
export const retryDocument = async (id: string) => api.post<any>(`/api/documents/${id}/retry`);
export const addDocumentFavorite = async (id: string) => api.put<void>(`/api/documents/${id}/favorite`);
export const removeDocumentFavorite = async (id: string) => api.delete<void>(`/api/documents/${id}/favorite`);

// Correspondents
export const getCorrespondents = async () => api.get<{ id: string; name: string }[]>("/api/correspondents");
export const createCorrespondent = async (name: string) => api.post<{ id: string; name: string }>("/api/correspondents", { name });

// Medications
export const getMedications = async (patientId: string, status?: string) => api.get<any[]>(`/api/patients/${patientId}/medications${status ? `?status=${status}` : ""}`);
export const createMedication = async (patientId: string, data: any) => api.post<any>(`/api/patients/${patientId}/medications`, data);
export const updateMedication = async (id: string, data: any) => api.put<any>(`/api/medications/${id}`, data);
export const deleteMedication = async (id: string) => api.delete<void>(`/api/medications/${id}`);

// Expenses
export const getExpenses = async (patientId: string, status?: string) => api.get<any[]>(`/api/patients/${patientId}/expenses${status ? `?status=${status}` : ""}`);
export const getExpenseSummary = async (patientId: string) => api.get<any>(`/api/patients/${patientId}/expenses/summary`);
export const createExpense = async (patientId: string, data: any) => api.post<any>(`/api/patients/${patientId}/expenses`, data);
export const updateExpense = async (id: string, data: any) => api.put<any>(`/api/expenses/${id}`, data);
export const confirmExpense = async (id: string) => api.post<any>(`/api/expenses/${id}/confirm`);
export const deleteExpense = async (id: string) => api.delete<void>(`/api/expenses/${id}`);
export const exportExpensesCsv = async (patientId: string) => requestText(`/api/patients/${patientId}/expenses/export.csv`);

// Einstufungen (Pflegegrad, ADR 042)
export const getEinstufungen = async (patientId: string) => api.get<Einstufung[]>(`/api/patients/${patientId}/einstufungen`);
export const getCurrentEinstufung = async (patientId: string) => api.get<Einstufung | null>(`/api/patients/${patientId}/einstufungen/current`);
export const getEinstufungScale = async (patientId: string) => api.get<Scale | null>(`/api/patients/${patientId}/einstufungen/scale`);
export const createEinstufung = async (patientId: string, data: EinstufungInput) => api.post<Einstufung>(`/api/patients/${patientId}/einstufungen`, data);
export const updateEinstufung = async (id: string, data: EinstufungInput) => api.put<Einstufung>(`/api/einstufungen/${id}`, data);
export const deleteEinstufung = async (id: string) => api.delete<void>(`/api/einstufungen/${id}`);

// Emergency Plan (ADR 048)
export const getEmergencyPlan = async (patientId: string) => api.get<EmergencyPlan | null>(`/api/patients/${patientId}/emergency-plan`);
export const saveEmergencyPlan = async (patientId: string, data: EmergencyPlanInput) => api.put<EmergencyPlan>(`/api/patients/${patientId}/emergency-plan`, data);

// Care Notes (ADR 048)
export const getCareNotes = async (patientId: string) => api.get<CareNotes | null>(`/api/patients/${patientId}/care-notes`);
export const saveCareNotes = async (patientId: string, data: CareNotes) => api.put<CareNotes>(`/api/patients/${patientId}/care-notes`, data);

// Carer Updates (ADR 049)
export const getCarerUpdates = async (patientId: string) => api.get<CarerUpdate[]>(`/api/patients/${patientId}/carer-updates`);
export const createCarerUpdate = async (patientId: string, data: CarerUpdateInput) => api.post<CarerUpdate>(`/api/patients/${patientId}/carer-updates`, data);
export const updateCarerUpdate = async (id: string, data: CarerUpdateInput) => api.put<CarerUpdate>(`/api/carer-updates/${id}`, data);
export const deleteCarerUpdate = async (id: string) => api.delete<void>(`/api/carer-updates/${id}`);

// Handouts (ADR 048)
export const getHandout = async (patientId: string, variant: string) => api.get<Handout>(`/api/patients/${patientId}/handouts/${variant}`);
export const downloadHandoutPdf = async (patientId: string, variant: string, exclude: string[], lang: string) =>
  requestBase64(`/api/patients/${patientId}/handouts/${variant}/pdf`, { exclude, lang });

// Conditions
export const getConditions = async (patientId: string, status?: string) => api.get<any[]>(`/api/patients/${patientId}/conditions${status ? `?status=${status}` : ""}`);
export const createCondition = async (patientId: string, data: any) => api.post<any>(`/api/patients/${patientId}/conditions`, data);
export const updateCondition = async (id: string, data: any) => api.put<any>(`/api/conditions/${id}`, data);
export const deleteCondition = async (id: string) => api.delete<void>(`/api/conditions/${id}`);
export const mergeCondition = async (winnerId: string, otherId: string) => api.post<any>(`/api/conditions/${winnerId}/merge`, { other_id: otherId });

// Incidents
export const getIncidents = async (patientId: string) => api.get<any[]>(`/api/patients/${patientId}/incidents`);
export const getIncidentSummary = async (patientId: string) => api.get<any>(`/api/patients/${patientId}/incidents/summary`);
export const createIncident = async (patientId: string, data: any) => api.post<any>(`/api/patients/${patientId}/incidents`, data);
export const updateIncident = async (id: string, data: any) => api.put<any>(`/api/incidents/${id}`, data);
export const deleteIncident = async (id: string) => api.delete<void>(`/api/incidents/${id}`);

// Calendar
export const getCalendarFeed = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<any[]>(`/api/patients/${patientId}/calendar/feed${q}`);
};
export const getCalendarTrends = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<any>(`/api/patients/${patientId}/calendar/trends${q}`);
};
export const getCalendarEvent = async (id: string) => api.get<any>(`/api/calendar/events/${id}`);
export const createCalendarEvent = async (patientId: string, data: any) => api.post<any>(`/api/patients/${patientId}/calendar/events`, data);
export const updateCalendarEvent = async (id: string, data: any) => api.put<any>(`/api/calendar/events/${id}`, data);
export const deleteCalendarEvent = async (id: string) => api.delete<void>(`/api/calendar/events/${id}`);

// Diary
export const getDiaryEntries = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<any[]>(`/api/patients/${patientId}/diary${q}`);
};
export const createDiaryEntry = async (patientId: string, data: any) => api.post<any>(`/api/patients/${patientId}/diary`, data);

// Groups
export const getGroups = async () => api.get<any[]>("/api/groups");
export const getGroup = async (id: string) => api.get<any>(`/api/groups/${id}`);
export const getGroupMembers = async (id: string) => api.get<any[]>(`/api/groups/${id}/members`);
export const createGroup = async (data: any) => api.post<any>("/api/groups", data);
export const inviteGroupMember = async (id: string, data: any) => api.post<any>(`/api/groups/${id}/members/invite`, data);
export const getGroupPatients = async (id: string) => api.get<any[]>(`/api/groups/${id}/patients`);


// User / account
export const getMe = async () => api.get<{ id: string; email: string; first_name: string | null; last_name: string | null; role: string; last_login_at: string | null }>("/api/auth/me");
export const updateMe = async (data: { first_name?: string; last_name?: string }) => api.patch<void>("/api/auth/me", data);
export const changePassword = async (currentPassword: string, newPassword: string) =>
  api.post<void>("/api/auth/me/password", { current_password: currentPassword, new_password: newPassword });

// Passkeys
export interface PasskeyInfo {
  id: string;
  label: string;
  aaguid: string | null;
  created_at: string;
  last_used_at: string | null;
}
export const getMyPasskeys = async () => api.get<PasskeyInfo[]>("/api/auth/passkey");
export const renamePasskey = async (id: string, label: string) => api.patch<void>(`/api/auth/passkey/${id}`, { label });
export const deletePasskeyApi = async (id: string) => api.delete<void>(`/api/auth/passkey/${id}`);

// Organization
export const getOrganization = async () => api.get<any>("/api/organization");

// Admin
export const getAdminUsers = async () => api.get<any[]>("/api/admin/users");
export const setUserRole = async (id: string, role: string) => api.post<any>(`/api/admin/users/${id}/role`, { role });
export const setUserActive = async (id: string, isActive: boolean) => api.post<any>(`/api/admin/users/${id}/active`, { is_active: isActive });
export const getAuditLogs = async (params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<any>(`/api/admin/audit${q}`);
};
export const getAdminInvitations = async () => api.get<any[]>("/api/admin/invitations");
export const createInvitation = async (email: string) => api.post<any>("/api/admin/invitations", { email });
export const revokeInvitation = async (id: string) => api.delete<void>(`/api/admin/invitations/${id}`);
export const removeMember = async (id: string) => api.post<any>(`/api/admin/users/${id}/remove`);
export const makeManager = async (id: string) => api.post<any>(`/api/admin/users/${id}/make-manager`);
export const getNotificationSettings = async () => api.get<any>("/api/admin/notification-settings");
export const updateNotificationSettings = async (patch: Record<string, boolean>) => api.put<any>("/api/admin/notification-settings", patch);
export const getAdminGroups = async () => api.get<any[]>("/api/admin/groups");
export const getAuditLog = async (params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<any>(`/api/admin/audit${q}`);
};
export const getOllamaStatus = async () => api.get<any>("/api/admin/ollama");

export const saveAiModelConfig = async (config: {
  extract_model?: string | null;
  classify_model?: string | null;
  chat_model?: string | null;
  vision_model?: string | null;
}) => api.put<{ ok: boolean }>("/api/admin/ollama/models", config);

export const getAdminPipelineTasks = async () => api.get<any[]>("/api/admin/logs/tasks");
export const getSystemInfo = async () => api.get<any>("/api/admin/system");

// Data sharing — Purpose Manager (Coordinator/admin)
export const getSharingPurposes = async () => api.get<any[]>("/api/sharing-purposes");
export const getSharingPurpose = async (id: string) => api.get<any>(`/api/sharing-purposes/${id}`);
export const getCollectedShares = async (id: string) => api.get<any[]>(`/api/sharing-purposes/${id}/shares`);

// Data sharing — Caregiver / patient side
export const getOpenShareRequests = async (patientId: string) => api.get<any[]>(`/api/patients/${patientId}/sharing/open-requests`);
export const getPatientShares = async (patientId: string) => api.get<any[]>(`/api/patients/${patientId}/sharing/shares`);

// External document share links (ADR-021)
export const getShareLinks = async (patientId: string) => api.get<any[]>(`/api/patients/${patientId}/share-links`);

// Intake Forms and History Facts (ADR 047); the upload goes through /api/intake-upload
export const getIntakeForms = async (patientId: string) => api.get<IntakeForm[]>(`/api/patients/${patientId}/intake-forms`);
export const getIntakeForm = async (id: string) => api.get<IntakeFormDetail>(`/api/intake-forms/${id}`);
export const answerIntakeItem = async (id: string, index: number, body: { answer?: string | null; aging?: Aging; confirm?: boolean }) =>
  api.put<IntakeFormDetail>(`/api/intake-forms/${id}/items/${index}`, body);
export const releaseIntakeForm = async (id: string) => api.post<IntakeFormDetail>(`/api/intake-forms/${id}/release`);
export const reviseIntakeForm = async (id: string) => api.post<IntakeForm>(`/api/intake-forms/${id}/revise`);
export const retryIntakeForm = async (id: string) => api.post<IntakeForm>(`/api/intake-forms/${id}/retry`);
export const deleteIntakeForm = async (id: string) => api.delete<void>(`/api/intake-forms/${id}`);
export const getHistoryFacts = async (patientId: string) => api.get<HistoryFact[]>(`/api/patients/${patientId}/history-facts`);
export const updateHistoryFact = async (id: string, body: { answer: string; aging: Aging }) =>
  api.put<HistoryFact>(`/api/history-facts/${id}`, body);
export const deleteHistoryFact = async (id: string) => api.delete<void>(`/api/history-facts/${id}`);

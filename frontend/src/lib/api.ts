"use server";

import { backendFetch } from "@/lib/backend";
import type { Einstufung, EinstufungInput, Scale } from "@/lib/einstufung";
import type { EmergencyPlan, EmergencyPlanInput } from "@/lib/emergencyPlan";
import type { CareNotes } from "@/lib/careNotes";
import type { CarerUpdate, CarerUpdateInput } from "@/lib/carerUpdates";
import type { Handout } from "@/lib/handout";
import type { Aging, HistoryFact, IntakeForm, IntakeFormDetail } from "@/lib/intake";
import type { CorrespondentReview, DiagnosisReview } from "@/lib/proposals";
import type { components } from "@/lib/api-schema";

// Generated from the backend's OpenAPI by `pnpm api-types`.
export type S<K extends keyof components["schemas"]> = components["schemas"][K];

export interface SystemInfo {
  runtime: {
    app_version: string;
    commit: string;
    python_version: string;
    platform: string;
    fastapi_version: string;
    pydantic_version: string;
    process_uptime: string;
    pid: number;
  };
  database: { version: string | null; size: string | null; tables: number | null };
  redis: { version?: string; used_memory_human?: string; connected_clients?: number; uptime_in_seconds?: number };
  storage: { total?: string; used?: string; free?: string; pct?: number };
  counts: { users: number; patients: number; documents: number };
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  // Never cache (backendFetch's default): a cached response once froze the admin
  // AI-backend status on "Disconnected" long after it recovered.
  const res = await backendFetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers as Record<string, string>) },
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API error ${res.status}: ${err}`);
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

// Like request() but returns the raw body as text — for CSV and other non-JSON downloads.
async function requestText(path: string): Promise<string> {
  const res = await backendFetch(path);
  if (!res.ok) throw new Error(`API error ${res.status}: ${await res.text()}`);
  return res.text();
}

async function requestBase64(path: string, body: unknown): Promise<string> {
  const res = await backendFetch(path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
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
export const getPatients = async (q?: string) => api.get<S<"PatientDto">[]>(`/api/patients${q ? `?q=${q}` : ""}`);
export const getFavoritePatients = async () => api.get<S<"PatientDto">[]>(`/api/patients/favorites`);
export const addFavorite = async (id: string) => api.put<void>(`/api/patients/${id}/favorite`);
export const removeFavorite = async (id: string) => api.delete<void>(`/api/patients/${id}/favorite`);
export const getPatient = async (id: string) => api.get<S<"PatientDto">>(`/api/patients/${id}`);

// Dashboard
export const getDashboard = async (patientId: string) => api.get<S<"PatientDashboardDto">>(`/api/patients/${patientId}/dashboard`);

// Observations
export const getObservations = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<S<"ObservationDto">[]>(`/api/patients/${patientId}/observations${q}`);
};
export const createObservation = async (patientId: string, data: S<"ObservationCreateRequest">) => api.post<S<"ObservationDto">>(`/api/patients/${patientId}/observations`, data);
export const deleteObservation = async (id: string) => api.delete<void>(`/api/observations/${id}`);

// Documents
export const getDocuments = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<S<"DocumentDto">[]>(`/api/patients/${patientId}/documents${q}`);
};
export const getDocumentDetail = async (id: string) => api.get<S<"DocumentDetailDto">>(`/api/documents/${id}/detail`);
export const verifyDocument = async (id: string, data: S<"VerifyDocumentRequest">) => api.post<S<"DocumentDetailDto">>(`/api/documents/${id}/verify`, data);
export const updateDocument = async (id: string, data: { issued_date?: string | null; description?: string | null; type?: string | null; correspondent_id?: string | null }) => api.patch<S<"DocumentDto">>(`/api/documents/${id}`, data);
export const deleteDocument = async (id: string) => api.delete<void>(`/api/documents/${id}`);
export const retryDocument = async (id: string) => api.post<{ job_id: string | null; stage: string }>(`/api/documents/${id}/retry`);

// What each letter adds over the earlier ones (ADR 058)
export const getDocumentNovelty = async (patientId: string) =>
  api.get<Record<string, import("@/app/patients/[id]/documents/DocumentsExplorer").Novelty>>(`/api/patients/${patientId}/documents/novelty`);

// Proposal Review (ADR 058)
export const getDiagnosisProposals = async (patientId: string) =>
  api.get<DiagnosisReview>(`/api/patients/${patientId}/proposals/diagnoses`);
export const getCorrespondentProposals = async (patientId: string) =>
  api.get<CorrespondentReview>(`/api/patients/${patientId}/proposals/correspondents`);
export const decideCorrespondentProposals = async (
  patientId: string,
  data: { document_ids: string[]; name: string; correspondent_id?: string | null },
) => api.post<void>(`/api/patients/${patientId}/proposals/correspondents/decide`, data);
export const decideDiagnosisProposals = async (
  patientId: string,
  data: { proposal_ids: string[]; accept: boolean; name?: string; condition_id?: string | null },
) => api.post<void>(`/api/patients/${patientId}/proposals/diagnoses/decide`, data);
export const addDocumentFavorite = async (id: string) => api.put<void>(`/api/documents/${id}/favorite`);
export const removeDocumentFavorite = async (id: string) => api.delete<void>(`/api/documents/${id}/favorite`);

// Correspondents
export const getCorrespondents = async () => api.get<{ id: string; name: string }[]>("/api/correspondents");
export const createCorrespondent = async (name: string) => api.post<{ id: string; name: string }>("/api/correspondents", { name });

// Medications
export const getMedications = async (patientId: string, status?: string) => api.get<S<"MedicationDto">[]>(`/api/patients/${patientId}/medications${status ? `?status=${status}` : ""}`);
export const createMedication = async (patientId: string, data: S<"MedicationCreateRequest">) => api.post<S<"MedicationDto">>(`/api/patients/${patientId}/medications`, data);
export const updateMedication = async (id: string, data: S<"MedicationUpdateRequest">) => api.put<S<"MedicationDto">>(`/api/medications/${id}`, data);
export const deleteMedication = async (id: string) => api.delete<void>(`/api/medications/${id}`);
// ADR 060
export const getDoses = async (patientId: string, since?: string) => api.get<S<"DoseDto">[]>(`/api/patients/${patientId}/doses${since ? `?since=${since}` : ""}`);
export const getIncidentDoses = async (patientId: string) => api.get<S<"DoseDto">[]>(`/api/patients/${patientId}/doses?with_incident=true`);
export const createDoses = async (patientId: string, data: S<"DoseIn">[]) => api.post<S<"DoseDto">[]>(`/api/patients/${patientId}/doses`, data);
export const updateDose = async (id: string, data: S<"DoseIn">) => api.put<S<"DoseDto">>(`/api/doses/${id}`, data);
export const deleteDose = async (id: string) => api.delete<void>(`/api/doses/${id}`);

// Expenses
export const getExpenses = async (patientId: string, status?: string) => api.get<S<"ExpenseDto">[]>(`/api/patients/${patientId}/expenses${status ? `?status=${status}` : ""}`);
export const getExpenseSummary = async (patientId: string) => api.get<S<"ExpenseSummaryDto">>(`/api/patients/${patientId}/expenses/summary`);
export const createExpense = async (patientId: string, data: S<"ExpenseCreateRequest">) => api.post<S<"ExpenseDto">>(`/api/patients/${patientId}/expenses`, data);
export const confirmExpense = async (id: string) => api.post<S<"ExpenseDto">>(`/api/expenses/${id}/confirm`);
export const deleteExpense = async (id: string) => api.delete<void>(`/api/expenses/${id}`);
export const exportExpensesCsv = async (patientId: string) => requestText(`/api/patients/${patientId}/expenses/export.csv`);

// Einstufungen (Pflegegrad, ADR 042)
export const getEinstufungen = async (patientId: string) => api.get<Einstufung[]>(`/api/patients/${patientId}/einstufungen`);
export const getCurrentEinstufung = async (patientId: string) => api.get<Einstufung | null>(`/api/patients/${patientId}/einstufungen/current`);
export const getEinstufungScale = async (patientId: string) => api.get<Scale | null>(`/api/patients/${patientId}/einstufungen/scale`);
export const createEinstufung = async (patientId: string, data: EinstufungInput) => api.post<Einstufung>(`/api/patients/${patientId}/einstufungen`, data);

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
export const getConditions = async (patientId: string, status?: string) => api.get<S<"ConditionDto">[]>(`/api/patients/${patientId}/conditions${status ? `?status=${status}` : ""}`);
export const updateCondition = async (id: string, data: S<"ConditionUpdateRequest">) => api.put<S<"ConditionDto">>(`/api/conditions/${id}`, data);
export const deleteCondition = async (id: string) => api.delete<void>(`/api/conditions/${id}`);
export const mergeCondition = async (winnerId: string, otherId: string) => api.post<S<"ConditionDto">>(`/api/conditions/${winnerId}/merge`, { other_id: otherId });

// Incidents
export const getIncidents = async (patientId: string) => api.get<S<"IncidentDto">[]>(`/api/patients/${patientId}/incidents`);
export const createIncident = async (patientId: string, data: S<"IncidentIn">) => api.post<S<"IncidentDto">>(`/api/patients/${patientId}/incidents`, data);
export const updateIncident = async (id: string, data: S<"IncidentIn">) => api.put<S<"IncidentDto">>(`/api/incidents/${id}`, data);
export const deleteIncident = async (id: string) => api.delete<void>(`/api/incidents/${id}`);

// Development (ADR 063)
export const getAbilities = async (patientId: string) => api.get<S<"AbilityDto">[]>(`/api/patients/${patientId}/abilities`);
export const updateAbility = async (id: string, data: S<"AbilityIn">) => api.put<S<"AbilityDto">>(`/api/abilities/${id}`, data);
export const createAbilityObservation = async (patientId: string, data: S<"AbilityObservationIn">) => api.post<S<"AbilityObservationDto">>(`/api/patients/${patientId}/ability-observations`, data);
export const updateAbilityObservation = async (id: string, data: S<"AbilityObservationIn">) => api.put<S<"AbilityObservationDto">>(`/api/ability-observations/${id}`, data);
export const deleteAbilityObservation = async (id: string) => api.delete<void>(`/api/ability-observations/${id}`);
export const getTestAttempts = async (patientId: string) => api.get<S<"TestAttemptDto">[]>(`/api/patients/${patientId}/test-attempts`);
export const createTestAttempt = async (patientId: string, data: S<"TestAttemptIn">) => api.post<S<"TestAttemptDto">>(`/api/patients/${patientId}/test-attempts`, data);
export const updateTestAttempt = async (id: string, data: S<"TestAttemptIn">) => api.put<S<"TestAttemptDto">>(`/api/test-attempts/${id}`, data);
export const deleteTestAttempt = async (id: string) => api.delete<void>(`/api/test-attempts/${id}`);

// Calendar
export const getCalendarFeed = async (patientId: string, params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<S<"CalendarFeedItem">[]>(`/api/patients/${patientId}/calendar/feed${q}`);
};
export const getCalendarEvent = async (id: string) => api.get<S<"CalendarEventDto">>(`/api/calendar/events/${id}`);
export const createCalendarEvent = async (patientId: string, data: S<"CalendarEventCreateRequest">) => api.post<S<"CalendarEventDto">>(`/api/patients/${patientId}/calendar/events`, data);
export const updateCalendarEvent = async (id: string, data: S<"CalendarEventUpdateRequest">) => api.put<S<"CalendarEventDto">>(`/api/calendar/events/${id}`, data);
export const deleteCalendarEvent = async (id: string) => api.delete<void>(`/api/calendar/events/${id}`);

// Diary

// Groups
export const getGroups = async () => api.get<S<"GroupListItemDto">[]>("/api/groups");
export const getGroup = async (id: string) => api.get<S<"GroupDto">>(`/api/groups/${id}`);
export const getGroupMembers = async (id: string) => api.get<S<"GroupMemberDto">[]>(`/api/groups/${id}/members`);
export const getGroupPatients = async (id: string) => api.get<S<"GroupPatientDto">[]>(`/api/groups/${id}/patients`);


// User / account
export const getMe = async () => api.get<{ id: string; email: string; first_name: string | null; last_name: string | null; role: string; last_login_at: string | null }>("/api/auth/me");
export const updateMe = async (data: { first_name?: string; last_name?: string }) => api.patch<void>("/api/auth/me", data);

// Passkeys
export interface PasskeyInfo {
  id: string;
  label: string;
  aaguid: string | null;
  created_at: string;
  last_used_at: string | null;
}
export const getMyPasskeys = async () => api.get<PasskeyInfo[]>("/api/auth/passkey");

// Organization
export const getOrganization = async () => api.get<S<"OrganizationDto">>("/api/organization");

// Admin
export const getAdminUsers = async () => api.get<S<"AdminUserDto">[]>("/api/admin/users");
export const getAdminInvitations = async () => api.get<S<"InvitationDto">[]>("/api/admin/invitations");
export const createInvitation = async (email: string) => api.post<S<"InvitationDto">>("/api/admin/invitations", { email });
export const revokeInvitation = async (id: string) => api.delete<void>(`/api/admin/invitations/${id}`);
export const removeMember = async (id: string) => api.post<{ ok: boolean }>(`/api/admin/users/${id}/remove`);
export const makeManager = async (id: string) => api.post<{ ok: boolean }>(`/api/admin/users/${id}/make-manager`);
export type NotificationSettings = {
  event_reminder: boolean;
  caregiver_added: boolean;
  invitation: boolean;
  include_content: boolean;
  document_processed: boolean;
};
export const getNotificationSettings = async () => api.get<NotificationSettings>("/api/admin/notification-settings");
export const updateNotificationSettings = async (patch: Partial<NotificationSettings>) => api.put<NotificationSettings>("/api/admin/notification-settings", patch);
export const getAdminGroups = async () => api.get<S<"AdminGroupDto">[]>("/api/admin/groups");
export const getAuditLog = async (params?: Record<string, string>) => {
  const q = params ? "?" + new URLSearchParams(params).toString() : "";
  return api.get<S<"PagedResult_AuditLogDto_">>(`/api/admin/audit${q}`);
};
export const getOllamaStatus = async () => api.get<S<"OllamaSettingsDto">>("/api/admin/ollama");


export const getSystemInfo = async () => api.get<SystemInfo>("/api/admin/system");

// Data sharing — Purpose Manager (Coordinator/admin)
export const getSharingPurposes = async () => api.get<S<"SharingPurposeDto">[]>("/api/sharing-purposes");
export const getSharingPurpose = async (id: string) => api.get<S<"SharingPurposeDto">>(`/api/sharing-purposes/${id}`);
export const getCollectedShares = async (id: string) => api.get<S<"CollectedShareDto">[]>(`/api/sharing-purposes/${id}/shares`);

// Data sharing — Caregiver / patient side
export const getOpenShareRequests = async (patientId: string) => api.get<S<"OpenRequestDto">[]>(`/api/patients/${patientId}/sharing/open-requests`);
export const getPatientShares = async (patientId: string) => api.get<S<"ShareDto">[]>(`/api/patients/${patientId}/sharing/shares`);

// External document share links (ADR-021)
export const getShareLinks = async (patientId: string) => api.get<S<"ShareLinkDto">[]>(`/api/patients/${patientId}/share-links`);

// Intake Forms and History Facts (ADR 047); the upload goes through /api/intake-upload
export const getIntakeForms = async (patientId: string) => api.get<IntakeForm[]>(`/api/patients/${patientId}/intake-forms`);
export const getIntakeForm = async (id: string) => api.get<IntakeFormDetail>(`/api/intake-forms/${id}`);
export type IntakeAnswer = { answer?: string | null; aging?: Aging; confirm?: boolean; observation?: S<"AbilityObservationIn"> };
export const answerIntakeItem = async (id: string, index: number, body: IntakeAnswer) =>
  api.put<IntakeFormDetail>(`/api/intake-forms/${id}/items/${index}`, body);
export const releaseIntakeForm = async (id: string) => api.post<IntakeFormDetail>(`/api/intake-forms/${id}/release`);
export const reviseIntakeForm = async (id: string) => api.post<IntakeForm>(`/api/intake-forms/${id}/revise`);
export const retryIntakeForm = async (id: string) => api.post<IntakeForm>(`/api/intake-forms/${id}/retry`);
export const deleteIntakeForm = async (id: string) => api.delete<void>(`/api/intake-forms/${id}`);
export const getHistoryFacts = async (patientId: string) => api.get<HistoryFact[]>(`/api/patients/${patientId}/history-facts`);
export const updateHistoryFact = async (id: string, body: { answer: string; aging: Aging }) =>
  api.put<HistoryFact>(`/api/history-facts/${id}`, body);
export const deleteHistoryFact = async (id: string) => api.delete<void>(`/api/history-facts/${id}`);

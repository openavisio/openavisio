// ADR 048

export interface PlanMedication {
  id: string;
  medication_display: string;
  dosage_text: string | null;
  dose_quantity: number | null;
  dose_unit: string | null;
  route: string | null;
  is_active: boolean;
}

export interface PlanDocument {
  id: string;
  description: string | null;
  file_name: string | null;
  issued_date: string | null;
  detected_provider: string | null;
  correspondent: { name: string } | null;
}

export interface PlanStep {
  text: string;
  medication_id?: string | null;
  // null with medication_id set: the Medication was deleted
  medication?: PlanMedication | null;
}

export interface PlanSituation {
  trigger: string;
  steps: PlanStep[];
}

export interface PlanContact {
  name: string;
  role?: string | null;
  phone?: string | null;
}

export interface EmergencyPlan {
  situations: PlanSituation[];
  contacts: PlanContact[];
  notes: string | null;
  documents: PlanDocument[];
}

export interface EmergencyPlanInput {
  situations: PlanSituation[];
  contacts: PlanContact[];
  notes: string | null;
  document_ids: string[];
}

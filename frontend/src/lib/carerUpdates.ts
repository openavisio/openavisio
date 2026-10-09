// ADR 049
export interface CarerUpdateInput {
  correspondent_id: string;
  person: string | null;
  day: string;
  text: string;
  retold: boolean;
}

export interface CarerUpdate extends CarerUpdateInput {
  id: string;
  correspondent_name: string;
}

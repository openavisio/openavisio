// Proposal Review (ADR 058): one group per condition or Correspondent, its spellings across letters.
export type ProposalDocument = { id: string; label: string | null; file_name: string | null; issued_date: string | null };
type Group<S> = { record: { id: string; name: string } | null; suggested_name: string; spellings: S[] };

// as the API sends them
export type DiagnosisSpelling = { name: string; proposal_ids: string[]; provisional: boolean; documents: ProposalDocument[] };
export type CorrespondentSpelling = { name: string; document_ids: string[]; documents: ProposalDocument[] };
export type DiagnosisReview = { grouped_by_model: boolean; groups: Group<DiagnosisSpelling>[] };
export type CorrespondentReview = { grouped_by_model: boolean; groups: Group<CorrespondentSpelling>[] };

// as the review shows them: ids are proposal ids for a diagnosis, document ids for a Correspondent
export type ReviewKind = "diagnosis" | "correspondent";
export type Spelling = { name: string; ids: string[]; provisional: boolean; documents: ProposalDocument[] };
export type ReviewGroup = Group<Spelling>;
export type Review = { grouped_by_model: boolean; groups: ReviewGroup[] };

export function fromDiagnoses(r: DiagnosisReview): Review {
  return { ...r, groups: r.groups.map((g) => ({ ...g, spellings: g.spellings.map((s) => ({ ...s, ids: s.proposal_ids })) })) };
}
export function fromCorrespondents(r: CorrespondentReview): Review {
  return { ...r, groups: r.groups.map((g) => ({ ...g, spellings: g.spellings.map((s) => ({ ...s, ids: s.document_ids, provisional: false })) })) };
}

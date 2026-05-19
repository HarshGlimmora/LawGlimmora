import { z } from "zod";

export const caseSchema = z
  .object({
    case_name: z.string().min(3, "Required").max(200),
    case_type: z.string().min(2),
    court_or_forum: z.string().min(2, "Required").max(120),
    jurisdiction: z.string().min(2),
    client_name: z.string().min(2, "Required").max(160),
    party_names: z.string().min(2, "List the parties.").max(2000),
    your_role_in_case: z.string().min(2),
    opposing_party_name: z.string().min(2, "Required").max(255),
    filing_date: z.string().min(1, "Pick a date."),
    next_hearing_date: z.string().optional().nullable(),
    urgency_level: z.string().min(2),
    confidentiality_level: z.string().min(2),
    case_status: z.string().min(2),
    short_case_summary: z.string().min(10, "Write at least one sentence.").max(4000),
    internal_notes: z.string().max(8000).optional().nullable(),
  })
  .refine(
    (v) => !v.next_hearing_date || v.next_hearing_date >= v.filing_date,
    { path: ["next_hearing_date"], message: "Hearing cannot be before filing." },
  );

export type CaseInput = z.infer<typeof caseSchema>;

/**
 * Centralised TanStack Query keys. Importing this in every hook keeps
 * invalidations consistent (one place to look when a key needs to change).
 */
export const qk = {
  me: ["auth", "me"] as const,
  constants: ["constants"] as const,
  profile: ["profile"] as const,
  cases: ["cases"] as const,
  caseDetail: (caseId: number) => ["cases", caseId] as const,
  evidenceDocuments: (caseId: number) => ["cases", caseId, "evidence", "documents"] as const,
  evidenceDocument: (caseId: number, docId: string) =>
    ["cases", caseId, "evidence", "documents", docId] as const,
  evidenceChat: (caseId: number) => ["cases", caseId, "evidence", "chat"] as const,
  evidenceChunks: (caseId: number) => ["cases", caseId, "evidence", "chunks"] as const,
  evidenceEntities: (caseId: number) => ["cases", caseId, "evidence", "entities"] as const,
  evidencePartitions: (caseId: number) => ["cases", caseId, "evidence", "partitions"] as const,
  evidenceContradictions: (caseId: number) =>
    ["cases", caseId, "evidence", "contradictions"] as const,
  evidenceMissing: (caseId: number) =>
    ["cases", caseId, "evidence", "missing"] as const,
  report: (caseId: number) => ["cases", caseId, "report"] as const,
  researchDocuments: (caseId: number) =>
    ["cases", caseId, "research", "documents"] as const,
  researchDocument: (caseId: number, docId: string) =>
    ["cases", caseId, "research", "documents", docId] as const,
  researchMetadata: (caseId: number) =>
    ["cases", caseId, "research", "metadata"] as const,
  researchSessions: (caseId: number) =>
    ["cases", caseId, "research", "sessions"] as const,
  researchSession: (caseId: number, sid: string) =>
    ["cases", caseId, "research", "sessions", sid] as const,
  researchDownstream: (caseId: number) =>
    ["cases", caseId, "research", "downstream"] as const,
  researchSimilar: (caseId: number, docId: string) =>
    ["cases", caseId, "research", "similar", docId] as const,
};

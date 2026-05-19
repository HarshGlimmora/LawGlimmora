/**
 * Typed wrappers around every backend route. UI never calls axios directly —
 * always go through these so the contract is enforced in one place.
 */
import { api, backendUrl } from "@/lib/api/client";
import type {
  AppConstants,
  Case,
  CasePayload,
  ChatPostResponse,
  ChatTurn,
  ChunkRecord,
  CitationLookupResponse,
  ContradictionItem,
  DownstreamPayload,
  EntityRecord,
  EvidenceDocumentSummary,
  ExtractionLog,
  EvidenceCanonical,
  FinalReportEnvelope,
  MetadataIndexRow,
  MissingEvidenceItem,
  Partition,
  PrecedentDocument,
  Profile,
  ProfilePayload,
  ResearchFeedbackBody,
  ResearchIngestTextBody,
  ResearchRunResponse,
  ResearchSaveSessionBody,
  ResearchSearchBody,
  ResearchSearchResponse,
  ResearchSession,
  ResearchUploadResponse,
  RetrievalContext,
  SessionUser,
  SimilarDocumentsResponse,
} from "@/types/api";

export const authEndpoints = {
  async me() {
    const { data } = await api.get<SessionUser>("/api/auth/me");
    return data;
  },
  async login(payload: { email: string; password: string }) {
    const { data } = await api.post<SessionUser>("/api/auth/login", payload);
    return data;
  },
  async signup(payload: { email: string; password: string; password_confirm: string }) {
    const { data } = await api.post<SessionUser>("/api/auth/signup", payload);
    return data;
  },
  async demoLogin(slug: "anika" | "vikram") {
    const { data } = await api.post<SessionUser>("/api/auth/demo-login", { slug });
    return data;
  },
  async logout() {
    await api.post("/api/auth/logout");
  },
};

export const constantsEndpoint = async (): Promise<AppConstants> => {
  const { data } = await api.get<AppConstants>("/api/constants");
  return data;
};

export const profileEndpoints = {
  async get() {
    const { data } = await api.get<Profile | Record<string, never>>("/api/profile");
    return Object.keys(data).length === 0 ? null : (data as Profile);
  },
  async save(payload: ProfilePayload) {
    const { data } = await api.put<Profile>("/api/profile", payload);
    return data;
  },
};

export const caseEndpoints = {
  async list() {
    const { data } = await api.get<Case[]>("/api/cases");
    return data;
  },
  async get(caseId: number) {
    const { data } = await api.get<Case>(`/api/cases/${caseId}`);
    return data;
  },
  async create(payload: CasePayload) {
    const { data } = await api.post<Case>("/api/cases", payload);
    return data;
  },
  async update(caseId: number, payload: CasePayload) {
    const { data } = await api.put<Case>(`/api/cases/${caseId}`, payload);
    return data;
  },
};

export const evidenceEndpoints = {
  async listDocuments(caseId: number) {
    const { data } = await api.get<EvidenceDocumentSummary[]>(
      `/api/cases/${caseId}/evidence/documents`,
    );
    return data;
  },
  async getDocument(caseId: number, documentId: string) {
    const { data } = await api.get<EvidenceCanonical>(
      `/api/cases/${caseId}/evidence/documents/${documentId}`,
    );
    return data;
  },
  async getLog(caseId: number, documentId: string) {
    const { data } = await api.get<ExtractionLog>(
      `/api/cases/${caseId}/evidence/documents/${documentId}/log`,
    );
    return data;
  },
  async upload(
    caseId: number,
    body: { file: File; evidence_title: string; doc_type: string; notes?: string },
  ) {
    const fd = new FormData();
    fd.append("file", body.file);
    fd.append("evidence_title", body.evidence_title);
    fd.append("doc_type", body.doc_type);
    if (body.notes) fd.append("notes", body.notes);
    const { data } = await api.post(`/api/cases/${caseId}/evidence/upload`, fd, {
      headers: { "Content-Type": "multipart/form-data" },
    });
    return data;
  },
  async search(caseId: number, body: { query: string; mode?: string; partition_filter?: string[] }) {
    const { data } = await api.post<RetrievalContext>(
      `/api/cases/${caseId}/evidence/search`,
      body,
    );
    return data;
  },
  async listChunks(caseId: number) {
    const { data } = await api.get<ChunkRecord[]>(
      `/api/cases/${caseId}/evidence/chunks`,
    );
    return data;
  },
  async listEntities(caseId: number) {
    const { data } = await api.get<EntityRecord[]>(
      `/api/cases/${caseId}/evidence/entities`,
    );
    return data;
  },
  async listPartitions(caseId: number) {
    const { data } = await api.get<Partition[]>(
      `/api/cases/${caseId}/evidence/partitions`,
    );
    return data;
  },
  async listContradictions(caseId: number) {
    const { data } = await api.get<ContradictionItem[]>(
      `/api/cases/${caseId}/evidence/contradictions`,
    );
    return data;
  },
  async listMissingEvidence(caseId: number) {
    const { data } = await api.get<MissingEvidenceItem[]>(
      `/api/cases/${caseId}/evidence/missing-evidence`,
    );
    return data;
  },
};

export const chatEndpoints = {
  async history(caseId: number) {
    const { data } = await api.get<{ case_id: string; turns: ChatTurn[] }>(
      `/api/cases/${caseId}/evidence/chat`,
    );
    return data;
  },
  async ask(caseId: number, body: { query: string; mode?: string; partition_filter?: string[] }) {
    const { data } = await api.post<ChatPostResponse>(
      `/api/cases/${caseId}/evidence/chat`,
      body,
    );
    return data;
  },
  async clear(caseId: number) {
    await api.delete(`/api/cases/${caseId}/evidence/chat`);
  },
};

export const researchEndpoints = {
  async listDocuments(caseId: number) {
    const { data } = await api.get<string[]>(`/api/cases/${caseId}/research/documents`);
    return data;
  },
  async getDocument(caseId: number, documentId: string) {
    const { data } = await api.get<PrecedentDocument>(
      `/api/cases/${caseId}/research/documents/${documentId}`,
    );
    return data;
  },
  async deleteDocument(caseId: number, documentId: string) {
    await api.delete(`/api/cases/${caseId}/research/documents/${documentId}`);
  },
  async uploadPdf(
    caseId: number,
    body: { file: File; notes?: string },
  ) {
    const fd = new FormData();
    fd.append("file", body.file);
    if (body.notes) fd.append("notes", body.notes);
    const { data } = await api.post<ResearchUploadResponse>(
      `/api/cases/${caseId}/research/upload`,
      fd,
      { headers: { "Content-Type": "multipart/form-data" } },
    );
    return data;
  },
  async ingestText(caseId: number, body: ResearchIngestTextBody) {
    const { data } = await api.post<ResearchUploadResponse>(
      `/api/cases/${caseId}/research/ingest-text`,
      body,
    );
    return data;
  },
  async enrich(caseId: number, documentId: string) {
    const { data } = await api.post(
      `/api/cases/${caseId}/research/documents/${documentId}/enrich`,
    );
    return data;
  },
  async rebuildIndex(caseId: number) {
    const { data } = await api.post(`/api/cases/${caseId}/research/index/rebuild`);
    return data;
  },
  async metadataIndex(caseId: number) {
    const { data } = await api.get<MetadataIndexRow[]>(
      `/api/cases/${caseId}/research/metadata`,
    );
    return data;
  },
  async lookupCitation(caseId: number, citation: string) {
    const { data } = await api.get<CitationLookupResponse>(
      `/api/cases/${caseId}/research/lookup/citation`,
      { params: { citation } },
    );
    return data;
  },
  async similar(caseId: number, documentId: string, topK = 10) {
    const { data } = await api.get<SimilarDocumentsResponse>(
      `/api/cases/${caseId}/research/documents/${documentId}/similar`,
      { params: { top_k: topK } },
    );
    return data;
  },
  async search(caseId: number, body: ResearchSearchBody) {
    const { data } = await api.post<ResearchSearchResponse>(
      `/api/cases/${caseId}/research/search`,
      body,
    );
    return data;
  },
  async run(caseId: number, body: ResearchSearchBody) {
    const { data } = await api.post<ResearchRunResponse>(
      `/api/cases/${caseId}/research/research`,
      body,
    );
    return data;
  },
  async listSessions(caseId: number) {
    const { data } = await api.get<ResearchSession[]>(
      `/api/cases/${caseId}/research/sessions`,
    );
    return data;
  },
  async getSession(caseId: number, sessionId: string) {
    const { data } = await api.get<ResearchSession>(
      `/api/cases/${caseId}/research/sessions/${sessionId}`,
    );
    return data;
  },
  async saveSession(caseId: number, body: ResearchSaveSessionBody) {
    const { data } = await api.post<{ ok: true; session_id: string }>(
      `/api/cases/${caseId}/research/sessions`,
      body,
    );
    return data;
  },
  async patchFeedback(caseId: number, sessionId: string, body: ResearchFeedbackBody) {
    const { data } = await api.patch<{ ok: true; session: ResearchSession }>(
      `/api/cases/${caseId}/research/sessions/${sessionId}/feedback`,
      body,
    );
    return data;
  },
  sessionExportUrl(caseId: number, sessionId: string, fmt: "json" | "markdown" | "pdf") {
    return backendUrl(`/api/cases/${caseId}/research/sessions/${sessionId}/export/${fmt}`);
  },
  async buildDownstream(caseId: number) {
    const { data } = await api.post<DownstreamPayload>(
      `/api/cases/${caseId}/research/downstream/build`,
    );
    return data;
  },
  async getDownstream(caseId: number) {
    const { data } = await api.get<DownstreamPayload>(
      `/api/cases/${caseId}/research/downstream`,
    );
    return data;
  },
};

export const reportEndpoints = {
  async get(caseId: number) {
    const { data } = await api.get<FinalReportEnvelope>(`/api/cases/${caseId}/report`);
    return data;
  },
  async generate(caseId: number) {
    const { data } = await api.post(`/api/cases/${caseId}/report/generate`);
    return data;
  },
  exportUrl(caseId: number, fmt: "json" | "text" | "pdf") {
    return backendUrl(`/api/cases/${caseId}/report/export/${fmt}`);
  },
};

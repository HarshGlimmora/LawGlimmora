// Wire types — mirror Pydantic models in glimmora_lawyer/modules/<pkg>/schemas/.
// Update both sides when fields change.

// ─── auth ────────────────────────────────────────────────────────────
export interface SessionUser {
  id: number;
  email: string;
  is_demo: boolean;
  has_profile: boolean;
}

// ─── constants (from config/constants.py + EVIDENCE_DOC_TYPES + SUGGESTED_PROMPTS) ─
export interface AppConstants {
  practice_areas: string[];
  indian_jurisdictions: string[];
  languages: string[];
  case_types: string[];
  roles_in_case: string[];
  urgency_levels: string[];
  confidentiality_levels: string[];
  case_statuses: string[];
  workspace_themes: string[];
  evidence_doc_types: string[];
  suggested_prompts: string[];
}

// ─── profile ─────────────────────────────────────────────────────────
export interface Profile {
  id: number;
  user_id: number;
  full_name: string;
  display_name: string;
  firm_name: string;
  role: string;
  practice_area: string;
  years_of_experience: number;
  jurisdiction_focus: string;
  city: string;
  preferred_languages: string; // CSV from backend
  bar_registration_id: string | null;
  phone: string | null;
  default_workspace_theme: string;
}

export interface ProfilePayload {
  full_name: string;
  display_name: string;
  email: string;
  firm_name: string;
  practice_area: string;
  years_of_experience: number;
  jurisdiction_focus: string;
  city: string;
  preferred_languages: string[];
  bar_registration_id?: string | null;
  phone?: string | null;
  default_workspace_theme: string;
}

// ─── case ────────────────────────────────────────────────────────────
export interface Case {
  id: number;
  user_id: number;
  case_name: string;
  case_type: string;
  court_or_forum: string;
  jurisdiction: string;
  client_name: string;
  party_names: string;
  your_role_in_case: string;
  opposing_party_name: string;
  filing_date: string; // ISO date
  next_hearing_date: string | null;
  urgency_level: string;
  confidentiality_level: string;
  case_status: string;
  short_case_summary: string;
  internal_notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface CasePayload {
  case_name: string;
  case_type: string;
  court_or_forum: string;
  jurisdiction: string;
  client_name: string;
  party_names: string;
  your_role_in_case: string;
  opposing_party_name: string;
  filing_date: string; // YYYY-MM-DD
  next_hearing_date?: string | null;
  urgency_level: string;
  confidentiality_level: string;
  case_status: string;
  short_case_summary: string;
  internal_notes?: string | null;
}

// ─── evidence ────────────────────────────────────────────────────────
export interface EvidenceDocumentSummary {
  document_id: string;
  filename: string;
  evidence_title: string;
  doc_type: string;
  uploaded_at: string;
  page_count: number;
  processing_status: "pending" | "extracting" | "completed" | "failed";
}

export interface CitationAnchor {
  citation_id: string;
  document_id: string;
  filename: string;
  page_number: number;
  citation_label: string;
}

export interface PageRecord {
  page_number: number;
  raw_text: string;
  clean_text: string;
  page_hash: string;
  character_count: number;
  word_count: number;
  citations: CitationAnchor[];
  entities: Record<string, unknown>[];
  claims: Record<string, unknown>[];
}

export interface DocumentMeta {
  document_id: string;
  case_id: string;
  filename: string;
  evidence_title: string;
  doc_type: string;
  source: string;
  language: string;
  jurisdiction: string;
  uploaded_at: string;
  page_count: number;
  processing_status: "pending" | "extracting" | "completed" | "failed";
  notes: string | null;
}

export interface EvidenceCanonical {
  document: DocumentMeta;
  pages: PageRecord[];
  chunks: Record<string, unknown>[];
  entities: Record<string, unknown>[];
  claims: Record<string, unknown>[];
  contradictions: Record<string, unknown>[];
  missing_evidence: Record<string, unknown>[];
  argument_recommendations: Record<string, unknown>[];
  summary: {
    total_pages: number;
    total_characters: number;
    total_words: number;
    extraction_duration_ms: number;
  };
}

export interface ExtractionLogStep {
  name: string;
  status: "ok" | "skipped" | "error";
  at: string;
  detail: string | null;
}

export interface ExtractionLog {
  document_id: string;
  case_id: string;
  filename: string;
  started_at: string;
  ended_at: string | null;
  duration_ms: number;
  page_count: number;
  result: "completed" | "failed";
  steps: ExtractionLogStep[];
  error: string | null;
}

// ─── retrieval / chat ────────────────────────────────────────────────
export interface RetrievalResult {
  result_id: string;
  result_type: "entity" | "chunk" | "contradiction" | "missing_evidence";
  title: string;
  snippet: string;
  source_document_id: string;
  source_chunk_id: string;
  source_page: number;
  citation_label: string;
  confidence: number;
  reason_retrieved: string;
}

export interface RetrievalContext {
  query: string;
  intent: string;
  mode: "entity-first" | "chunk-first" | "hybrid";
  partition_filter: string[] | null;
  entity_hits: RetrievalResult[];
  chunk_hits: RetrievalResult[];
  contradiction_hits: RetrievalResult[];
  missing_hits: RetrievalResult[];
  all_results: RetrievalResult[];
  debug: Record<string, unknown>;
}

export interface SupportingSource {
  citation_label: string;
  document_id: string;
  chunk_id: string;
  page: number;
  snippet: string;
}

export interface Answer {
  answer_id: string;
  query: string;
  intent: string;
  final_answer: string;
  supporting_sources: SupportingSource[];
  confidence: number;
  warnings: string[];
  retrieval_summary: Record<string, number>;
  why_retrieved: string;
  next_question: string;
  generated_at: string;
  synthesis_source: string;
}

export interface ChatTurn {
  turn_id: string;
  role: "user" | "assistant";
  ts: string;
  message: string;
  answer_id: string | null;
  intent: string | null;
  citations: Record<string, unknown>[];
}

export interface ChatPostResponse {
  answer: Answer;
  context: RetrievalContext;
}

// ─── chunks / entities / partitions ──────────────────────────────────
export interface ChunkCitationAnchor {
  citation_id: string;
  document_id: string;
  filename: string;
  page_start: number;
  page_end: number;
  chunk_index: number;
  char_start: number;
  char_end: number;
  citation_label: string;
}

export interface ChunkRecord {
  chunk_id: string;
  document_id: string;
  page_start: number;
  page_end: number;
  chunk_index: number;
  chunk_type: string;
  text: string;
  clean_text: string;
  embedding_ready_text: string;
  word_count: number;
  character_count: number;
  citation_anchor: ChunkCitationAnchor;
  entities: string[];      // entity_ids
  claims: unknown[];
  confidence: number;
}

export interface EntityRecord {
  entity_id: string;
  entity_type: string;
  value: string;
  normalized_value: string;
  context_excerpt: string;
  confidence: number;
  document_id: string;
  source_chunk_id: string;
  source_page: number;
  citation_label: string;
}

export interface Partition {
  partition_type: "parties" | "timeline" | "legal_basis" | "factual_evidence" | "procedural_facts" | string;
  entities: EntityRecord[];
}

// ─── contradictions + missing evidence ───────────────────────────────
export type Severity = "low" | "medium" | "high" | "critical";

export interface ContradictionItem {
  id: string;
  kind: string;
  severity: Severity;
  summary: string;
  explanation: string;
  references: string[];                // citation labels
}

export interface MissingEvidenceItem {
  id: string;
  category: string;
  severity: Severity;
  why_it_matters: string;
  recommendation: string;
}

// ─── report ──────────────────────────────────────────────────────────
export interface ScoreSet {
  evidence_strength_score: number;
  evidence_weakness_score: number;
  completeness_score: number;
  contradiction_risk_score: number;
  missing_evidence_risk_score: number;
  timeline_integrity_score: number;
  legal_basis_strength_score: number;
  readiness_score: number;
  pitch_success_estimate: number;
}

export interface EvidencePoint {
  title: string;
  snippet: string;
  citation_label: string;
  chunk_id: string;
  document_id: string;
  page: number;
  score: number;
}

export interface ContradictionSummary {
  contradiction_id: string;
  kind: string;
  severity: Severity;
  summary: string;
  explanation: string;
  references: string[];
}

export interface MissingEvidenceSummary {
  missing_id: string;
  category: string;
  severity: Severity;
  why_it_matters: string;
  recommendation: string;
}

export interface IssueSummary {
  issue_name: string;
  support_level: number;
  contradiction_impact: number;
  missing_evidence_impact: number;
  related_entities: string[];
  related_chunks: string[];
  legal_significance: string;
  recommended_action: string;
}

export interface Recommendation {
  recommendation_id: string;
  title: string;
  description: string;
  priority: "low" | "medium" | "high" | "critical";
  related_issue: string;
  related_contradiction_ids: string[];
  related_missing_ids: string[];
  related_chunk_ids: string[];
  action_type: "upload" | "verify" | "clarify" | "strengthen" | "review" | "summarize";
}

export interface SourceMapEntry {
  label: string;
  document_id: string;
  chunk_id: string;
  page_number: number;
  reason_used: string;
}

export interface FinalReport {
  report_id: string;
  case_id: string;
  generated_at: string;
  scores: ScoreSet;
  executive_summary: string;
  strongest_issue: string;
  weakest_issue: string;
  strongest_points: EvidencePoint[];
  weakest_points: EvidencePoint[];
  contradiction_summary: ContradictionSummary[];
  missing_evidence_summary: MissingEvidenceSummary[];
  issue_matrix: IssueSummary[];
  recommendations: Recommendation[];
  final_conclusion: string;
  source_map: SourceMapEntry[];
  narrative_source: "vertex" | "aistudio" | "fallback";
}

export interface FinalReportEnvelope {
  report: FinalReport | null;
  dashboard: {
    case_id?: string;
    report_id?: string;
    generated_at?: string;
    narrative_source?: string;
    strongest_issue?: string;
    weakest_issue?: string;
    scores?: ScoreSet;
    counts?: Record<string, number>;
  } | null;
}

// ═══ Package 2: Research & Precedent Engine ══════════════════════════
// Mirrors glimmora_lawyer/modules/research_engine/schemas/.
// Update both sides if these shapes change.

export type PrecedentBindingLevel = "binding" | "persuasive" | "informational";
export type PrecedentSourceType =
  | "pdf_upload"
  | "plain_text"
  | "seeded_corpus"
  | "api";
export type PrecedentIngestionStatus =
  | "pending"
  | "extracted"
  | "enriched"
  | "indexed"
  | "failed";

export interface PrecedentMeta {
  document_id: string;
  title: string;
  citation: string;
  court: string;
  judges: string[];
  date_decided: string | null;
  jurisdiction: string;
  practice_areas: string[];
  issue_tags: string[];
  outcome: string | null;
  binding_level: PrecedentBindingLevel;
  headnote: string | null;
  ratio: string | null;
  source_type: PrecedentSourceType;
  source_reference: string;
  confidence_score: number;
}

export interface PrecedentPage {
  page_number: number;
  text: string;
}

export interface PrecedentDocument {
  document_id: string;
  case_id: string;
  filename: string;
  ingested_at: string;
  page_count: number;
  full_text: string;
  pages: PrecedentPage[];
  meta: PrecedentMeta;
  status: PrecedentIngestionStatus;
  chunks_built: boolean;
  indexed: boolean;
  notes: string | null;
}

export interface MetadataIndexRow {
  document_id: string;
  title: string;
  citation: string;
  court: string;
  judges: string[];
  date_decided: string | null;
  jurisdiction: string;
  practice_areas: string[];
  issue_tags: string[];
  outcome: string | null;
  binding_level: PrecedentBindingLevel;
  page_count: number;
  filename: string;
}

export interface ResearchScoreBreakdown {
  jurisdiction_match: number;
  court_rank: number;
  issue_overlap: number;
  fact_similarity: number;
  outcome_alignment: number;
  recency: number;
  authority_level: number;
  doctrinal_relevance: number;
}

export interface RankedHit {
  chunk_id: string;
  document_id: string;
  final_score: number;
  breakdown: ResearchScoreBreakdown;
  snippet: string;
  citation_label: string;
  page_start: number;
  page_end: number;
  chunk_type: string;
  paragraph_anchor: string;
  document_title: string;
  document_citation: string;
  document_court: string;
  document_date: string | null;
  binding_level: PrecedentBindingLevel;
}

export type ResearchQueryType = "legal_question" | "fact_pattern";

export interface ResearchQuery {
  query_text: string;
  query_type: ResearchQueryType;
  jurisdiction_filter: string | null;
  court_filter: string[];
  issue_filter: string[];
  practice_area_filter: string[];
  date_range: [string | null, string | null] | null;
  top_k: number;
}

export type SupportingAuthorityTier = "strongest" | "distinguishable";

export interface SupportingAuthority {
  document_id: string;
  title: string;
  citation: string;
  court: string;
  date_decided: string | null;
  binding_level: PrecedentBindingLevel;
  relevance_summary: string;
  top_chunk_citation_label: string;
  similarity_score: number;
  risk_flags: string[];
  tier: SupportingAuthorityTier;
  distinguishing_reason: string;
}

export interface ResearchExcerpt {
  citation_label: string;
  document_id: string;
  chunk_id: string;
  page_start: number;
  page_end: number;
  snippet: string;
}

export interface ResearchAnswer {
  answer_id: string;
  query_text: string;
  query_type: string;
  top_answer: string;
  applicable_law: string[];
  strongest_authorities: SupportingAuthority[];
  distinguishable_authorities: SupportingAuthority[];
  authorities: SupportingAuthority[];   // back-compat alias = strongest
  excerpts: ResearchExcerpt[];
  risk_flags: string[];
  confidence: number;
  retrieval_summary: Record<string, number>;
  synthesis_source: "vertex" | "aistudio" | "fallback";
  generated_at: string;
  next_question: string;
  next_steps: string[];
}

export interface ResearchSession {
  session_id: string;
  case_id: string;
  query_text: string;
  query_type: string;
  created_at: string;
  answer: ResearchAnswer;
  ranked_hits: RankedHit[];
  user_notes: string;
  pinned_document_ids: string[];
  user_feedback: "thumbs_up" | "thumbs_down" | "neutral";
  unresolved_questions: string[];
}

export interface ResearchSearchResponse {
  query: ResearchQuery;
  hits_retrieved: number;
  ranked: RankedHit[];
}

export interface ResearchRunResponse {
  query: ResearchQuery;
  answer: ResearchAnswer;
  ranked: RankedHit[];
}

export interface CitationLookupResponse {
  citation_query: string;
  matches: MetadataIndexRow[];
}

export interface SimilarDocumentsResponse {
  seed_document_id: string;
  results: RankedHit[];
}

export interface DownstreamTimelineItem {
  date: string;
  event: string;
  source_document_id: string;
  source_citation_label: string;
}

export interface DownstreamPayload {
  case_id: string;
  generated_at: string;
  top_authorities: SupportingAuthority[];
  timeline_items: DownstreamTimelineItem[];
  case_strength_signals: Record<string, number>;
  unresolved_legal_issues: string[];
  session_count: number;
  corpus_doc_count: number;
  notes: string | null;
}

export interface ResearchUploadResponse {
  document_id: string;
  duplicate_filename_warning: boolean;
  chunk_count: number;
  metadata: PrecedentMeta;
  ingestion_log: Record<string, unknown>;
  index_summary: { docs: number; chunks: number; vocab_size: number; avgdl: number };
}

export interface ResearchIngestTextBody {
  title: string;
  body: string;
  source_reference?: string;
  notes?: string | null;
}

export interface ResearchSearchBody {
  query_text: string;
  query_type?: ResearchQueryType;
  jurisdiction_filter?: string | null;
  court_filter?: string[];
  issue_filter?: string[];
  practice_area_filter?: string[];
  date_from?: string | null;
  date_to?: string | null;
  top_k?: number;
}

export interface ResearchSaveSessionBody {
  answer_id: string;
  query_text: string;
  query_type: string;
  ranked_hits: RankedHit[];
  answer: ResearchAnswer;
  user_notes?: string;
  pinned_document_ids?: string[];
  unresolved_questions?: string[];
}

export interface ResearchFeedbackBody {
  pinned_document_ids?: string[] | null;
  user_feedback?: "thumbs_up" | "thumbs_down" | "neutral" | null;
  unresolved_questions?: string[] | null;
  user_notes?: string | null;
}

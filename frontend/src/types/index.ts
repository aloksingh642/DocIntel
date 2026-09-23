export interface User { id: number; name: string; email: string; role: string }

export interface Document {
  id: number; filename: string; file_type: string; file_size: number;
  document_type: string | null; classification_confidence: number | null;
  extraction_confidence: number | null; processing_status: string;
  processing_error: string | null; is_duplicate: boolean;
  duplicate_type: string | null; duplicate_similarity: number | null;
  duplicate_of_id: number | null; candidate_id: number | null;
  created_at: string | null; processed_at: string | null;
}

export interface ProcessingLog {
  id: number; stage: string; status: string; message: string | null;
  processing_time: number | null; created_at: string | null;
}

export interface Page<T> { items: T[]; total: number; page: number; page_size: number; pages: number }

export interface CandidateSummary {
  id: number; name: string | null; email: string | null; phone: string | null;
  location: string | null; total_experience_years: number | null; skills: string[];
  status: string; tags: string[];
  created_at: string | null;
  score?: number;
}

export interface CandidateNote {
  id: number; text: string; user_id: number | null; created_at: string | null;
}

export interface CandidateProfile extends CandidateSummary {
  linkedin: string | null; github: string | null; portfolio: string | null;
  professional_summary: string | null;
  experiences: { id: number; company: string | null; job_title: string | null; description: string | null }[];
  education: { id: number; institution: string | null; degree: string | null; field: string | null; end_year: number | null }[];
  certifications: { id: number; name: string; issuer: string | null }[];
  projects: { id: number; name: string; description: string | null; technologies: string | null }[];
  notes: CandidateNote[];
  documents: { id: number; filename: string; document_type: string | null; processing_status: string }[];
  skill_matches: { job_id: number; match_percentage: number; matched_skills: string[]; missing_skills: string[] }[];
}

export interface Job {
  id: number; title: string; description: string | null;
  required_skills: string[]; nice_to_have_skills: string[]; created_at: string | null;
}

export interface MatchResult {
  candidate_id: number; candidate_name: string | null; match_percentage: number;
  matched_skills: string[]; missing_skills: string[];
  matched_nice: string[]; missing_nice: string[]; formula: string;
}

export interface RuntimeSetting {
  key: string; value: number; default: number; label: string; help: string;
  overridden: boolean; min: number | null; max: number | null;
}

export interface WebhookRow {
  id: number; url: string; event: string; active: boolean; has_secret: boolean;
  delivery_count: number;
  last_delivery: { success: boolean; status_code: number | null; error: string | null; created_at: string | null } | null;
}

export const CANDIDATE_STATUSES = [
  "new", "reviewing", "shortlisted", "interviewed", "offer", "hired", "rejected",
] as const;

export interface Overview {
  total_documents: number; processed_documents: number; failed_documents: number;
  needs_review_documents: number; total_candidates: number; duplicate_documents: number;
  average_stage_time_seconds: number | null; total_jobs: number; total_skills: number;
}

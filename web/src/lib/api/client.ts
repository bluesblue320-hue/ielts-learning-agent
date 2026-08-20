export type WritingSkill =
  | "task_response"
  | "coherence_and_cohesion"
  | "lexical_resource"
  | "grammatical_range_and_accuracy";

export type BandScore = { value: string };

export type ApiErrorPayload = {
  error: { code: string; message: string; fields: string[] };
};

export class ApiRequestError extends Error {
  readonly status: number;
  readonly code: string;
  readonly fields: string[];

  constructor(status: number, payload: ApiErrorPayload["error"]) {
    super(payload.message);
    this.name = "ApiRequestError";
    this.status = status;
    this.code = payload.code;
    this.fields = payload.fields;
  }
}

export type Learner = {
  id: number;
  writing_target_band: BandScore;
  created_at: string;
  updated_at: string;
};

export type LearnerSkillState = {
  learner_id: number;
  skill: WritingSkill;
  estimated_band: string | null;
  evidence_count: number;
  last_evidence_id: number | null;
  state_policy_version: string;
  revision: number;
  updated_at: string;
};

export type LearnerStateResponse = {
  learner_id: number;
  states: Record<WritingSkill, LearnerSkillState>;
};

export type WritingCriteria = Record<
  WritingSkill,
  { band: BandScore; evidence: string[]; feedback: string }
>;

export type WritingEvaluation = {
  criteria: WritingCriteria;
  strengths: string[];
  weaknesses: string[];
  error_tags: string[];
  recommended_skills: string[];
  feedback: string;
  metadata: {
    provider: string;
    model: string;
    prompt_version: string;
    rubric_version: string;
    scoring_policy_version: string;
    thinking_mode: "enabled" | "disabled";
  };
  word_count: number;
  product_band: BandScore;
};

export type WritingEvaluationResponse = {
  attempt_id: number;
  evaluation_id: number;
  evaluation: WritingEvaluation;
};

export type PlanningExplanationFactor =
  | "equal_maximum_target_gap"
  | "persistent_gap_tiebreak"
  | "trend_tiebreak"
  | "lower_recent_practice_count"
  | "canonical_priority_tiebreak";

export type PlanningExplanation = {
  factors: PlanningExplanationFactor[];
};

type PracticeRecommendationBase = {
  decision_type: "practice" | "no_practice";
  target_skill: WritingSkill | null;
  learner_target_band: BandScore | null;
  current_estimate: string | null;
  reason_codes: string[];
  state_snapshot: Record<WritingSkill, LearnerSkillState>;
};

export type PracticeRecommendationV1 = PracticeRecommendationBase & {
  planner_version: "writing-practice-gap-v1";
};

export type PracticeRecommendationV2 = PracticeRecommendationBase & {
  planner_version: "writing-practice-gap-memory-v2";
  planning_explanation: PlanningExplanation | null;
};

export type PracticeRecommendation =
  | PracticeRecommendationV1
  | PracticeRecommendationV2;

export type LearningApplyResponse = {
  learning_update_id: number;
  reused: boolean;
  recommendation_id: number;
  recommendation: PracticeRecommendation;
};

export type PracticeResponse = {
  id: number;
  learner_id: number;
  recommendation_id: number;
  target_skill: WritingSkill;
  question: string;
  focus_objective: string;
  instructions: string[];
  checkpoints: string[];
  practice_type: string;
  generator_policy_version: string;
  provider: string;
  model: string;
  prompt_version: string;
  thinking_mode: string;
  lifecycle_state: "generated" | "submission_in_progress" | "submitted";
  attempt_id: number | null;
  created_at: string;
  updated_at: string;
};

export type GenerationOutcome = {
  decision: "practice" | "no_practice";
  practice: PracticeResponse | null;
  no_practice_reasons: string[];
};

export type SubmissionResult = {
  status: "submitted" | "reused" | "conflict" | "in_progress";
  attempt_id: number | null;
  evaluation_id: number | null;
};

export type ClosedLoopResult = {
  practice_id: number;
  attempt_id: number;
  evaluation_id: number;
  learning_update_id: number;
  next_recommendation_id: number;
  next_recommendation: PracticeRecommendation;
};

// --- Phase 6 hierarchical learning memory read contracts (P6-09) ----------
// These types mirror the frozen backend read models. The browser never
// recomputes trend / persistent gap / resume action / ownership / episode
// type; those are backend authority.

export type EpisodeType = "initial_writing" | "targeted_practice";
export type TrendStatus =
  | "improving"
  | "stable"
  | "declining"
  | "insufficient_history";
export type PersistentGapStatus = "established" | "insufficient_history";
export type ResumeAction =
  | "initial_writing"
  | "no_action"
  | "generate_practice"
  | "submit_practice"
  | "await_submission"
  | "complete_practice";

export type EpisodeSkillObservation = {
  skill: WritingSkill;
  observed_band: BandScore;
  learning_evidence_id: number;
  source_attempt_id: number;
  source_created_at: string;
};

export type EpisodeSkillObservationSet = Record<WritingSkill, EpisodeSkillObservation>;

export type LearningEpisodeSummary = {
  episode_id: number;
  episode_type: EpisodeType;
  occurred_at: string;
  writing_evaluation_id: number;
  attempt_id: number;
  writing_practice_id: number | null;
  /** The completed practice's actual target (null for initial_writing). */
  practice_target_skill: WritingSkill | null;
  recommendation_id: number;
  recommendation_decision_type: "practice" | "no_practice";
  recommendation_target_skill: WritingSkill | null;
  recommendation_reason_codes: string[];
  planner_version: string;
  skill_observations: EpisodeSkillObservationSet;
};

export type WritingHistoryResponse = {
  learner_id: number;
  episodes: LearningEpisodeSummary[];
};

export type LearningEvidenceView = {
  id: number;
  learning_update_id: number;
  learner_id: number;
  writing_evaluation_id: number;
  skill: WritingSkill;
  observed_band: BandScore;
  source_created_at: string;
  source_attempt_id: number;
  provider: string;
  model: string;
  prompt_version: string;
  rubric_version: string;
  scoring_policy_version: string;
  thinking_mode: "enabled" | "disabled";
  created_at: string;
};

export type LearningUpdateView = {
  id: number;
  learner_id: number;
  writing_evaluation_id: number;
  skill_taxonomy_version: string;
  state_policy_version: string;
  planner_version: string;
  created_at: string;
};

export type WritingAttemptView = {
  attempt_id: number;
  question: string;
  essay: string;
  word_count: number;
  created_at: string;
};

export type LearningEpisodeDetail = {
  episode: LearningEpisodeSummary;
  learning_update: LearningUpdateView;
  attempt: WritingAttemptView;
  evaluation: WritingEvaluationResponse;
  evidence: LearningEvidenceView[];
  recommendation: PracticeRecommendation;
  practice: PracticeResponse | null;
};

export type SkillProgress = {
  learner_id: number;
  skill: WritingSkill;
  policy_version: "writing-progress-v1";
  current_estimate: string | null;
  evidence_count: number;
  trend: TrendStatus;
  persistent_gap: boolean;
  persistent_gap_status: PersistentGapStatus;
  recent_observation_count: number;
  recent_practice_count: number;
  latest_observation_time: string | null;
  last_episode_id: number | null;
  /** Evidence ids of the canonical trend window that produced trend/gap. */
  source_observation_ids: number[];
  /** LearningUpdate ids OWNING the trend-window evidence rows (exact L0). */
  source_episode_ids: number[];
  /** Latest RECENT_PRACTICE_EPISODE_WINDOW episode ids (practice provenance). */
  recent_practice_source_episode_ids: number[];
};

export type SkillProgressSet = Record<WritingSkill, SkillProgress>;

export type WritingProgressResponse = {
  learner_id: number;
  current_writing_target_band: BandScore;
  current_state: LearnerStateResponse["states"];
  skills: SkillProgressSet;
  memory_version: "writing-memory-v1";
  progress_version: "writing-progress-v1";
};

export type WritingContextResponse = {
  learner_id: number;
  resume_action: ResumeAction;
  has_learner_owned_episodes: boolean;
  latest_learning_update_id: number | null;
  current_recommendation_id: number | null;
  current_recommendation: PracticeRecommendation | null;
  relevant_practice: PracticeResponse | null;
  current_state: LearnerStateResponse["states"];
};

export type AgentTurnRequest =
  | { turn_type: "continue" }
  | { turn_type: "practice_submission"; practice_id: number; essay: string };
export type AgentObservationKind = "needs_initial_writing" | "no_practice" | "needs_generation" | "needs_practice_submission" | "await_submission" | "needs_completion";
export type AgentObservation = { kind: AgentObservationKind; no_practice_reason_codes: string[] | null };
export type AgentTool = "observe" | "generate_practice" | "submit_practice" | "complete_practice";
export type AgentOutcome = "observation_classified" | "practice_generated" | "practice_resolved" | "generation_stale_discarded" | "submission_submitted" | "submission_reused" | "submission_in_progress" | "submission_conflict" | "completion_applied" | "completion_reused";
export type AgentTurnResponse = { agent_version: "writing-core-learning-agent-v1"; initial_observation: AgentObservation; steps: { tool: AgentTool; outcome: AgentOutcome }[]; final_observation: AgentObservation; stop_reason: "needs_initial_writing" | "needs_practice_submission" | "practice_ready" | "await_submission" | "target_achieved" | "no_practice" | "submission_conflict" | "max_actions"; current_recommendation: PracticeRecommendation | null; current_practice: PracticeResponse | null };
type FetchLike = typeof fetch;
type RequestOptions = Omit<RequestInit, "body" | "method"> & {
  body?: unknown;
  method?: "GET" | "POST";
};

export type ApiClientOptions = {
  baseUrl?: string;
  fetch?: FetchLike;
};

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

function errorPayload(value: unknown): ApiErrorPayload["error"] {
  if (
    typeof value === "object" &&
    value !== null &&
    "error" in value &&
    typeof value.error === "object" &&
    value.error !== null &&
    "code" in value.error &&
    "message" in value.error
  ) {
    const error = value.error as Partial<ApiErrorPayload["error"]>;
    if (typeof error.code === "string" && typeof error.message === "string") {
      return {
        code: error.code,
        message: error.message,
        fields: Array.isArray(error.fields)
          ? error.fields.filter((field): field is string => typeof field === "string")
          : [],
      };
    }
  }

  return {
    code: "unexpected_response",
    message: "The learning service returned an unexpected response.",
    fields: [],
  };
}

export function createApiClient(options: ApiClientOptions = {}) {
  const baseUrl = normalizeBaseUrl(
    options.baseUrl ?? process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000",
  );
  const requestFetch = options.fetch ?? fetch;

  async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
    const { body, method = "GET", headers, ...init } = options;
    const response = await requestFetch(`${baseUrl}${path}`, {
      ...init,
      method,
      headers: body === undefined
        ? headers
        : { "Content-Type": "application/json", ...headers },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
    const payload: unknown = await response.json().catch(() => null);

    if (!response.ok) {
      throw new ApiRequestError(response.status, errorPayload(payload));
    }

    return payload as T;
  }

  return {
    createLearner: (writingTargetBand: string) =>
      request<Learner>("/learners", {
        method: "POST",
        body: { writing_target_band: { value: writingTargetBand } },
      }),
    getLearnerState: (learnerId: number) =>
      request<LearnerStateResponse>(`/learners/${learnerId}/state`),
    evaluateWriting: (question: string, essay: string) =>
      request<WritingEvaluationResponse>("/writing/evaluate", {
        method: "POST",
        body: { question, essay },
      }),
    applyEvaluation: (learnerId: number, evaluationId: number) =>
      request<LearningApplyResponse>(
        `/learners/${learnerId}/writing/evaluations/${evaluationId}/apply`,
        { method: "POST" },
      ),
    generatePractice: (learnerId: number, recommendationId: number) =>
      request<GenerationOutcome>(
        `/learners/${learnerId}/writing/recommendations/${recommendationId}/practice`,
        { method: "POST" },
      ),
    getPractice: (learnerId: number, practiceId: number) =>
      request<PracticeResponse>(`/learners/${learnerId}/writing/practices/${practiceId}`),
    submitPractice: (learnerId: number, practiceId: number, essay: string) =>
      request<SubmissionResult>(
        `/learners/${learnerId}/writing/practices/${practiceId}/submit`,
        { method: "POST", body: { essay } },
      ),
    getPracticeEvaluation: (learnerId: number, practiceId: number) =>
      request<WritingEvaluationResponse>(
        `/learners/${learnerId}/writing/practices/${practiceId}/evaluation`,
      ),
    completePractice: (learnerId: number, practiceId: number) =>
      request<ClosedLoopResult>(
        `/learners/${learnerId}/writing/practices/${practiceId}/complete`,
        { method: "POST" },
      ),
    getWritingHistory: (learnerId: number) =>
      request<WritingHistoryResponse>(`/learners/${learnerId}/writing/history`),
    getWritingHistoryEpisode: (learnerId: number, episodeId: number) =>
      request<LearningEpisodeDetail>(
        `/learners/${learnerId}/writing/history/${episodeId}`,
      ),
    getWritingProgress: (learnerId: number) =>
      request<WritingProgressResponse>(`/learners/${learnerId}/writing/progress`),
    getWritingContext: (learnerId: number) =>
      request<WritingContextResponse>(`/learners/${learnerId}/writing/context`),
    agentTurn: (learnerId: number, input: AgentTurnRequest) =>
      request<AgentTurnResponse>(`/learners/${learnerId}/agent/turn`, { method: "POST", body: input }),
  };
}

export const apiClient = createApiClient();

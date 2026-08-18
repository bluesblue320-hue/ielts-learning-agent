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

export type PracticeRecommendation = {
  decision_type: "practice" | "no_practice";
  target_skill: WritingSkill | null;
  learner_target_band: BandScore | null;
  current_estimate: string | null;
  reason_codes: string[];
  planner_version: string;
  state_snapshot: Record<WritingSkill, LearnerSkillState>;
};

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
  };
}

export const apiClient = createApiClient();

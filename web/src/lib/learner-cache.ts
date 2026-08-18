import type { PracticeRecommendation } from "./api/client.ts";

export type LearnerPresentationCache = {
  currentLearnerId: number;
  writingTargetBand: string;
  currentRecommendationId: number | null;
  currentRecommendation: PracticeRecommendation | null;
};

type StorageLike = Pick<Storage, "getItem" | "setItem" | "removeItem">;

const CACHE_KEY = "ielts-learning-agent.phase5.presentation";

function isPositiveInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isInteger(value) && value > 0;
}

export function readLearnerPresentationCache(
  storage: StorageLike | null,
): LearnerPresentationCache | null {
  if (storage === null) return null;

  try {
    const raw = storage.getItem(CACHE_KEY);
    if (raw === null) return null;
    const value: unknown = JSON.parse(raw);
    if (typeof value !== "object" || value === null) return null;
    const cache = value as Partial<LearnerPresentationCache>;
    if (
      !isPositiveInteger(cache.currentLearnerId) ||
      typeof cache.writingTargetBand !== "string" ||
      (cache.currentRecommendationId !== null &&
        !isPositiveInteger(cache.currentRecommendationId))
    ) {
      return null;
    }
    return {
      currentLearnerId: cache.currentLearnerId,
      writingTargetBand: cache.writingTargetBand,
      currentRecommendationId: cache.currentRecommendationId ?? null,
      currentRecommendation: cache.currentRecommendation ?? null,
    };
  } catch {
    return null;
  }
}

export function writeLearnerPresentationCache(
  storage: StorageLike | null,
  cache: LearnerPresentationCache | null,
): void {
  if (storage === null) return;
  if (cache === null) {
    storage.removeItem(CACHE_KEY);
    return;
  }
  storage.setItem(CACHE_KEY, JSON.stringify(cache));
}

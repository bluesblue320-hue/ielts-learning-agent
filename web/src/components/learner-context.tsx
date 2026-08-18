"use client";

import { createContext, useContext, useEffect, useMemo, useState } from "react";

import type { PracticeRecommendation } from "@/lib/api/client";
import {
  readLearnerPresentationCache,
  writeLearnerPresentationCache,
  type LearnerPresentationCache,
} from "@/lib/learner-cache";

type LearnerContextValue = {
  cache: LearnerPresentationCache | null;
  isReady: boolean;
  setLearner: (learnerId: number, writingTargetBand: string) => void;
  setRecommendation: (
    recommendationId: number,
    recommendation: PracticeRecommendation,
  ) => void;
  clearLearner: () => void;
};

const LearnerContext = createContext<LearnerContextValue | null>(null);

function browserStorage(): Storage | null {
  return typeof window === "undefined" ? null : window.localStorage;
}

export function LearnerProvider({ children }: { children: React.ReactNode }) {
  const [cache, setCache] = useState<LearnerPresentationCache | null>(null);
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      setCache(readLearnerPresentationCache(browserStorage()));
      setIsReady(true);
    }, 0);
    return () => window.clearTimeout(timer);
  }, []);

  const value = useMemo<LearnerContextValue>(() => ({
    cache,
    isReady,
    setLearner: (currentLearnerId, writingTargetBand) => {
      const next = {
        currentLearnerId,
        writingTargetBand,
        currentRecommendationId: null,
        currentRecommendation: null,
      };
      setCache(next);
      writeLearnerPresentationCache(browserStorage(), next);
    },
    setRecommendation: (currentRecommendationId, currentRecommendation) => {
      if (cache === null) return;
      const next = { ...cache, currentRecommendationId, currentRecommendation };
      setCache(next);
      writeLearnerPresentationCache(browserStorage(), next);
    },
    clearLearner: () => {
      setCache(null);
      writeLearnerPresentationCache(browserStorage(), null);
    },
  }), [cache, isReady]);

  return <LearnerContext value={value}>{children}</LearnerContext>;
}

export function useLearnerContext(): LearnerContextValue {
  const value = useContext(LearnerContext);
  if (value === null) {
    throw new Error("useLearnerContext must be used within LearnerProvider");
  }
  return value;
}

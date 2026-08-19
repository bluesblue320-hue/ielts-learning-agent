"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { type LearnerStateResponse, type WritingSkill, apiClient, type WritingContextResponse } from "@/lib/api/client";
import { useLearnerContext } from "@/components/learner-context";
import { presentApiError, presentNoPracticeReasons, presentPracticeReasons, skillLabels } from "@/lib/presentation";
import { resumeActionExplanations, resumeActionLabels } from "@/lib/memory-presentation";

export default function DashboardPage() {
  const router = useRouter();
  const { cache, isReady } = useLearnerContext();
  const [state, setState] = useState<LearnerStateResponse | null>(null);
  const [context, setContext] = useState<WritingContextResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const learnerId = cache?.currentLearnerId ?? null;

  useEffect(() => {
    if (!isReady || learnerId === null) return;
    const activeLearnerId: number = learnerId;
    let active = true;
    async function loadState() {
      try {
        const result = await apiClient.getLearnerState(activeLearnerId);
        if (active) setState(result);
      } catch (reason) {
        if (active) setError(presentApiError(reason));
      }
    }
    async function loadContext() {
      try {
        const result = await apiClient.getWritingContext(activeLearnerId);
        if (active) setContext(result);
      } catch (reason) {
        if (active) setError(presentApiError(reason));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    async function load() {
      setIsLoading(true);
      setError(null);
      // Load state and context independently so a resume-context failure does
      // not blank the authoritative state grid.
      await Promise.all([loadState(), loadContext()]);
    }
    void load();
    return () => { active = false; };
  }, [isReady, learnerId]);

  async function generatePractice() {
    if (context === null || context.current_recommendation_id === null) return;
    const activeLearnerId = context.learner_id;
    const recommendationId = context.current_recommendation_id;
    setIsGenerating(true);
    setError(null);
    try {
      const outcome = await apiClient.generatePractice(activeLearnerId, recommendationId);
      if (outcome.decision === "practice" && outcome.practice !== null) {
        router.push(`/practice/${outcome.practice.id}`);
        return;
      }
      setError("当前没有需要生成的针对性练习。");
    } catch (reason) {
      setError(presentApiError(reason));
    } finally {
      setIsGenerating(false);
    }
  }

  function renderResumeAction() {
    if (context === null) return null;
    const action = context.resume_action;
    if (action === "initial_writing") {
      return <><p className="supporting-copy">{resumeActionExplanations.initial_writing}</p><Link className="primary-action" href="/writing">开始首次写作</Link></>;
    }
    if (action === "no_action") {
      return <p className="supporting-copy">{resumeActionExplanations.no_action}</p>;
    }
    if (action === "generate_practice") {
      return (
        <>
          <p className="supporting-copy">{resumeActionExplanations.generate_practice}</p>
          {context.current_recommendation?.target_skill !== null && (
            <p className="supporting-copy">
              训练重点：{context.current_recommendation?.target_skill === undefined ? "—" : skillLabels[context.current_recommendation.target_skill]}
            </p>
          )}
          <button className="primary-action" disabled={isGenerating} onClick={generatePractice} type="button">
            {isGenerating ? "正在生成练习…" : "生成针对性练习"}
          </button>
        </>
      );
    }
    if (context.relevant_practice !== null && (action === "submit_practice" || action === "complete_practice")) {
      return (
        <>
          <p className="supporting-copy">{resumeActionExplanations[action]}</p>
          <p className="supporting-copy">训练重点：{skillLabels[context.relevant_practice.target_skill]}</p>
          <Link className="primary-action" href={`/practice/${context.relevant_practice.id}`}>
            {resumeActionLabels[action]}
          </Link>
        </>
      );
    }
    return <p className="supporting-copy">{resumeActionExplanations[action]}</p>;
  }

  if (!isReady) return <p className="status-copy" aria-live="polite">正在恢复学习进度…</p>;
  if (cache === null) {
    return (
      <section className="content-card narrow-card">
        <h1>先设置学习目标</h1>
        <p className="supporting-copy">选择目标分数后，就可以开始首次 Writing Task 2 写作。</p>
        <Link className="primary-action" href="/setup">前往学习设置</Link>
      </section>
    );
  }

  return (
    <section>
      <p className="eyebrow">学习概览</p>
      <h1>你的写作学习状态</h1>
      <p className="supporting-copy">目标分数：{cache.writingTargetBand}</p>
      {isLoading && <p className="status-copy" aria-live="polite">正在读取学习状态…</p>}
      {error !== null && <p className="error-message" role="alert">{error}</p>}
      {state !== null && (
        <div className="state-grid">
          {(Object.keys(skillLabels) as WritingSkill[]).map((skill) => {
            const item = state.states[skill];
            return (
              <article className="content-card" key={skill}>
                <h2>{skillLabels[skill]}</h2>
                <p className="metric">{item.estimated_band ?? "尚未评估"}</p>
                <p className="supporting-copy">已采纳证据：{item.evidence_count}</p>
              </article>
            );
          })}
        </div>
      )}
      <section className="content-card next-step">
        <h2>继续学习</h2>
        {context === null ? (
          <><p className="supporting-copy">正在读取下一步建议…</p><Link className="primary-action" href="/writing">进行首次写作</Link></>
        ) : (
          renderResumeAction()
        )}
        {context?.current_recommendation?.decision_type === "no_practice" && (
          <p className="supporting-copy">{presentNoPracticeReasons(context.current_recommendation.reason_codes)}</p>
        )}
        {context?.current_recommendation?.decision_type === "practice" && (
          <p className="supporting-copy">{presentPracticeReasons(context.current_recommendation.reason_codes)}</p>
        )}
      </section>
      <p className="supporting-copy nav-hint">
        <Link href="/history">查看写作历史</Link> · <Link href="/progress">查看学习进度</Link>
      </p>
    </section>
  );
}

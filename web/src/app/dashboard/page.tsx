"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import { type LearnerStateResponse, type WritingSkill, apiClient } from "@/lib/api/client";
import { useLearnerContext } from "@/components/learner-context";
import { presentApiError, presentNoPracticeReasons, presentPracticeReasons, skillLabels } from "@/lib/presentation";

export default function DashboardPage() {
  const router = useRouter();
  const { cache, isReady } = useLearnerContext();
  const [state, setState] = useState<LearnerStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const learnerId = cache?.currentLearnerId ?? null;
  const [isGenerating, setIsGenerating] = useState(false);

  useEffect(() => {
    if (!isReady || learnerId === null) return;
    const activeLearnerId: number = learnerId;
    let active = true;
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const result = await apiClient.getLearnerState(activeLearnerId);
        if (active) setState(result);
      } catch (reason) {
        if (active) setError(presentApiError(reason));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [isReady, learnerId]);

  async function generatePractice() {
    if (cache === null || cache.currentRecommendationId === null) return;
    const activeLearnerId = cache.currentLearnerId;
    const recommendationId = cache.currentRecommendationId;
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
        <h2>下一步</h2>
        {cache.currentRecommendation === null ? (
          <><p className="supporting-copy">完成首次写作评估并应用学习更新后，系统会在此显示下一步建议。</p><Link className="primary-action" href="/writing">进行首次写作</Link></>
        ) : cache.currentRecommendation.decision_type === "no_practice" ? (
          <p className="supporting-copy">{presentNoPracticeReasons(cache.currentRecommendation.reason_codes)}</p>
        ) : (
          <><p className="supporting-copy">训练重点：{cache.currentRecommendation.target_skill === null ? "—" : skillLabels[cache.currentRecommendation.target_skill]}</p><p className="supporting-copy">当前估计：{cache.currentRecommendation.current_estimate ?? "尚未建立"}；目标分数：{cache.currentRecommendation.learner_target_band?.value ?? cache.writingTargetBand}</p><p className="supporting-copy">{presentPracticeReasons(cache.currentRecommendation.reason_codes)}</p><button className="primary-action" disabled={isGenerating} onClick={generatePractice} type="button">{isGenerating ? "正在生成练习…" : "生成针对性练习"}</button></>
        )}
      </section>
    </section>
  );
}

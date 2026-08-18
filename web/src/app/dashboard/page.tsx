"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiRequestError, type LearnerStateResponse, type WritingSkill, apiClient } from "@/lib/api/client";
import { useLearnerContext } from "@/components/learner-context";

const labels: Record<WritingSkill, string> = {
  task_response: "任务回应（Task Response）",
  coherence_and_cohesion: "连贯与衔接（Coherence and Cohesion）",
  lexical_resource: "词汇资源（Lexical Resource）",
  grammatical_range_and_accuracy: "语法多样性与准确性（Grammatical Range and Accuracy）",
};

function stateMessage(reason: unknown): string {
  if (reason instanceof ApiRequestError && reason.code === "learner_not_found") {
    return "未找到当前学习者，请重新设置学习目标。";
  }
  return "暂时无法读取学习状态，请刷新后重试。";
}

export default function DashboardPage() {
  const { cache, isReady } = useLearnerContext();
  const [state, setState] = useState<LearnerStateResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const learnerId = cache?.currentLearnerId ?? null;

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
        if (active) setError(stateMessage(reason));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [isReady, learnerId]);

  if (!isReady) return <p className="status-copy">正在恢复学习进度…</p>;
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
      {isLoading && <p className="status-copy">正在读取学习状态…</p>}
      {error !== null && <p className="error-message" role="alert">{error}</p>}
      {state !== null && (
        <div className="state-grid">
          {(Object.keys(labels) as WritingSkill[]).map((skill) => {
            const item = state.states[skill];
            return (
              <article className="content-card" key={skill}>
                <h2>{labels[skill]}</h2>
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
          <p className="supporting-copy">完成首次写作评估并应用学习更新后，系统会在此显示下一步建议。</p>
        ) : (
          <p className="supporting-copy">已收到新的练习建议。请继续查看并选择下一步操作。</p>
        )}
        <Link className="primary-action" href="/writing">进行首次写作</Link>
      </section>
    </section>
  );
}

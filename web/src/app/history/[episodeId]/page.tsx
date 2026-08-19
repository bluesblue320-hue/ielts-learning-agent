"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { useLearnerContext } from "@/components/learner-context";
import { apiClient, type LearningEpisodeDetail, type WritingSkill } from "@/lib/api/client";
import { episodeTypeLabels, formatEpisodeTime } from "@/lib/memory-presentation";
import { presentApiError, presentPlanningExplanation, presentPracticeReasons, skillLabels } from "@/lib/presentation";

export default function EpisodeDetailPage() {
  const params = useParams<{ episodeId: string }>();
  const episodeId = Number(params.episodeId);
  const { cache, isReady } = useLearnerContext();
  const [detail, setDetail] = useState<LearningEpisodeDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const learnerId = cache?.currentLearnerId ?? null;
  const planningExplanation = presentPlanningExplanation(detail?.recommendation);

  useEffect(() => {
    if (!isReady || learnerId === null || !Number.isInteger(episodeId)) return;
    const activeLearnerId = learnerId;
    let active = true;
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const result = await apiClient.getWritingHistoryEpisode(activeLearnerId, episodeId);
        if (active) setDetail(result);
      } catch (reason) {
        if (active) setError(presentApiError(reason));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [isReady, learnerId, episodeId]);

  if (!isReady) return <p className="status-copy" aria-live="polite">正在恢复学习进度…</p>;
  if (cache === null) {
    return (
      <section className="content-card narrow-card">
        <h1>学习记录详情</h1>
        <p className="supporting-copy">先设置学习目标，再查看历史记录。</p>
        <Link className="primary-action" href="/setup">前往学习设置</Link>
      </section>
    );
  }

  return (
    <section>
      <p className="eyebrow">学习记忆</p>
      <h1>学习记录详情</h1>
      {isLoading && <p className="status-copy" aria-live="polite">正在读取记录详情…</p>}
      {error !== null && <p className="error-message" role="alert">{error}</p>}
      {detail !== null && (
        <>
          <p className="supporting-copy">
            {episodeTypeLabels[detail.episode.episode_type]} · {formatEpisodeTime(detail.episode.occurred_at)}
          </p>

          <section className="content-card detail-section">
            <h2>写作题目</h2>
            <p className="question-copy">{detail.attempt.question}</p>
            <h2>你的作文</h2>
            <p className="essay-copy">{detail.attempt.essay}</p>
            <p className="supporting-copy">字数：{detail.attempt.word_count} · 综合分数：{detail.evaluation.evaluation.product_band.value}</p>
          </section>

          <section className="content-card detail-section">
            <h2>四项评分</h2>
            {(Object.keys(skillLabels) as WritingSkill[]).map((skill) => {
              const criterion = detail.evaluation.evaluation.criteria[skill];
              return (
                <article className="criterion-block" key={skill}>
                  <h3>
                    {skillLabels[skill]}
                    <span className="criterion-band"> {criterion.band.value}</span>
                  </h3>
                  {criterion.evidence.length > 0 && (
                    <p className="supporting-copy">依据：{criterion.evidence.join("；")}</p>
                  )}
                  <p className="supporting-copy">{criterion.feedback}</p>
                </article>
              );
            })}
          </section>

          <section className="content-card detail-section">
            <h2>总体反馈</h2>
            <p className="feedback-copy">{detail.evaluation.evaluation.feedback}</p>
            {detail.evaluation.evaluation.strengths.length > 0 && (
              <p className="supporting-copy"><strong>优点：</strong>{detail.evaluation.evaluation.strengths.join("；")}</p>
            )}
            {detail.evaluation.evaluation.weaknesses.length > 0 && (
              <p className="supporting-copy"><strong>待改进：</strong>{detail.evaluation.evaluation.weaknesses.join("；")}</p>
            )}
            {detail.evaluation.evaluation.error_tags.length > 0 && (
              <p className="supporting-copy"><strong>常见问题：</strong>{detail.evaluation.evaluation.error_tags.join("；")}</p>
            )}
            {detail.evaluation.evaluation.recommended_skills.length > 0 && (
              <p className="supporting-copy"><strong>建议练习：</strong>{detail.evaluation.evaluation.recommended_skills.join("；")}</p>
            )}
          </section>

          {detail.practice !== null && (
            <section className="content-card detail-section">
              <h2>针对性练习</h2>
              <p className="supporting-copy">训练重点：{skillLabels[detail.practice.target_skill]}</p>
              <p className="question-copy">{detail.practice.question}</p>
              <p className="supporting-copy">目标：{detail.practice.focus_objective}</p>
              <p className="supporting-copy">状态：{detail.practice.lifecycle_state}</p>
              {detail.practice.checkpoints.length > 0 && (
                <ul className="plain-list">
                  {detail.practice.checkpoints.map((checkpoint) => (
                    <li key={checkpoint}>{checkpoint}</li>
                  ))}
                </ul>
              )}
            </section>
          )}

          <section className="content-card detail-section">
            <h2>下一步建议</h2>
            <p className="supporting-copy">
              {presentPracticeReasons(detail.recommendation.reason_codes)}
            </p>
            {detail.recommendation.decision_type === "practice"
              ? `训练重点：${detail.recommendation.target_skill === null ? "—" : skillLabels[detail.recommendation.target_skill]}`
              : "本次没有针对性练习建议。"}
            {planningExplanation !== null && (
              <p className="supporting-copy" role="status">
                推荐依据：{planningExplanation}
              </p>
            )}
          </section>

          <details className="audit-details">
            <summary>记录来源信息</summary>
            <ul className="plain-list">
              <li>学习记录编号：{detail.episode.episode_id}</li>
              <li>评估编号：{detail.episode.writing_evaluation_id}</li>
              <li>提交编号：{detail.episode.attempt_id}</li>
              {detail.episode.writing_practice_id !== null && <li>练习编号：{detail.episode.writing_practice_id}</li>}
              <li>建议编号：{detail.episode.recommendation_id}</li>
            </ul>
          </details>

          <p className="back-link">
            <Link href="/history">← 返回写作历史</Link>
          </p>
        </>
      )}
    </section>
  );
}

"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useLearnerContext } from "@/components/learner-context";
import { apiClient, type SkillProgress, type WritingProgressResponse, type WritingSkill } from "@/lib/api/client";
import {
  persistentGapLabels,
  progressSourceLinkLabel,
  trendExplanations,
  trendLabels,
} from "@/lib/memory-presentation";
import { presentApiError, skillLabels } from "@/lib/presentation";

function ProgressCard({ skill, target }: { skill: SkillProgress; target: string }) {
  return (
    <article className="content-card progress-card">
      <h2>{skillLabels[skill.skill]}</h2>
      <p className="progress-metrics">
        当前估计：<span className="metric-inline">{skill.current_estimate ?? "尚未评估"}</span>
        <span className="metric-sep">目标：{target}</span>
      </p>
      <p className={`trend-badge trend-${skill.trend}`}>{trendLabels[skill.trend]}</p>
      <p className="supporting-copy">{trendExplanations[skill.trend]}</p>
      <ul className="progress-facts">
        <li>
          持续低于目标：
          <strong className={skill.persistent_gap ? "gap-true" : "gap-false"}>
            {skill.persistent_gap_status === "insufficient_history"
              ? persistentGapLabels.insufficient_history
              : skill.persistent_gap
                ? "是"
                : "否"}
          </strong>
        </li>
        <li>已采纳证据：{skill.evidence_count}</li>
        <li>近三次观测：{skill.recent_observation_count}</li>
        <li>近期完成练习：{skill.recent_practice_count}</li>
      </ul>
      {skill.source_episode_ids.length > 0 && (
        <p className="drill-down">
          {[...new Set(skill.source_episode_ids)].map((episodeId, index) => (
            <Link className="drill-down-link" href={`/history/${episodeId}`} key={episodeId}>
              {progressSourceLinkLabel(index)}
            </Link>
          ))}
        </p>
      )}
    </article>
  );
}

export default function ProgressPage() {
  const { cache, isReady } = useLearnerContext();
  const [progress, setProgress] = useState<WritingProgressResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const learnerId = cache?.currentLearnerId ?? null;

  useEffect(() => {
    if (!isReady || learnerId === null) return;
    const activeLearnerId = learnerId;
    let active = true;
    async function load() {
      setIsLoading(true);
      setError(null);
      try {
        const result = await apiClient.getWritingProgress(activeLearnerId);
        if (active) setProgress(result);
      } catch (reason) {
        if (active) setError(presentApiError(reason));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void load();
    return () => { active = false; };
  }, [isReady, learnerId]);

  if (!isReady) return <p className="status-copy" aria-live="polite">正在恢复学习进度…</p>;
  if (cache === null) {
    return (
      <section className="content-card narrow-card">
        <h1>学习进度</h1>
        <p className="supporting-copy">先设置学习目标，再查看长期进步趋势。</p>
        <Link className="primary-action" href="/setup">前往学习设置</Link>
      </section>
    );
  }

  async function retry() {
    if (learnerId === null) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await apiClient.getWritingProgress(learnerId);
      setProgress(result);
    } catch (reason) {
      setError(presentApiError(reason));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section>
      <p className="eyebrow">纵向进步</p>
      <h1>学习进度</h1>
      {isLoading && <p className="status-copy" aria-live="polite">正在读取学习进度…</p>}
      {error !== null && (
        <p className="error-message" role="alert">{error}</p>
      )}
      {error !== null && (
        <button className="retry-action" onClick={retry} type="button">重试</button>
      )}
      {progress !== null && (
        <>
          <p className="supporting-copy">
            当前目标分数：{progress.current_writing_target_band.value}。趋势基于最近三次评估判断。
          </p>
          <div className="progress-grid">
            {(Object.keys(skillLabels) as WritingSkill[]).map((skill) => (
              <ProgressCard
                key={skill}
                skill={progress.skills[skill]}
                target={progress.current_writing_target_band.value}
              />
            ))}
          </div>
        </>
      )}
    </section>
  );
}

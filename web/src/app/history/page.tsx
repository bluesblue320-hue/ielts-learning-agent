"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { useLearnerContext } from "@/components/learner-context";
import { apiClient, type LearningEpisodeSummary, type WritingSkill } from "@/lib/api/client";
import { episodeTypeLabels, formatEpisodeTime } from "@/lib/memory-presentation";
import { presentApiError, skillLabels } from "@/lib/presentation";

export default function HistoryPage() {
  const { cache, isReady } = useLearnerContext();
  const [episodes, setEpisodes] = useState<LearningEpisodeSummary[] | null>(null);
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
        const result = await apiClient.getWritingHistory(activeLearnerId);
        if (active) setEpisodes(result.episodes);
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
        <h1>写作历史</h1>
        <p className="supporting-copy">先设置学习目标并完成首次写作，系统会在这里记录每次学习活动。</p>
        <Link className="primary-action" href="/setup">前往学习设置</Link>
      </section>
    );
  }

  async function retry() {
    if (learnerId === null) return;
    setIsLoading(true);
    setError(null);
    try {
      const result = await apiClient.getWritingHistory(learnerId);
      setEpisodes(result.episodes);
    } catch (reason) {
      setError(presentApiError(reason));
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <section>
      <p className="eyebrow">学习记忆</p>
      <h1>写作历史</h1>
      <p className="supporting-copy">这里按时间倒序记录你每次完成的写作评估与针对性练习。</p>
      {isLoading && <p className="status-copy" aria-live="polite">正在读取学习历史…</p>}
      {error !== null && (
        <p className="error-message" role="alert">{error}</p>
      )}
      {error !== null && (
        <button className="retry-action" onClick={retry} type="button">重试</button>
      )}
      {episodes !== null && episodes.length === 0 && !isLoading && (
        <p className="supporting-copy">还没有学习记录。完成首次写作评估并应用学习更新后，记录会出现在这里。</p>
      )}
      <ul className="episode-list">
        {episodes?.map((episode) => (
          <li className="content-card episode-card" key={episode.episode_id}>
            <Link className="episode-link" href={`/history/${episode.episode_id}`}>
              <h2>
                <span className={`episode-type episode-type-${episode.episode_type}`}>
                  {episodeTypeLabels[episode.episode_type]}
                </span>
                <span className="episode-time">{formatEpisodeTime(episode.occurred_at)}</span>
              </h2>
              <ul className="episode-bands">
                {(Object.keys(skillLabels) as WritingSkill[]).map((skill) => (
                  <li key={skill}>
                    <span className="episode-band-label">{skillLabels[skill]}</span>
                    <span className="episode-band-value">{episode.skill_observations[skill].observed_band.value}</span>
                  </li>
                ))}
              </ul>
              <p className="supporting-copy">
                {episode.recommendation_decision_type === "practice"
                  ? `训练建议：${episode.recommendation_target_skill === null ? "—" : skillLabels[episode.recommendation_target_skill]}`
                  : "本次暂无针对性练习建议"}
              </p>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

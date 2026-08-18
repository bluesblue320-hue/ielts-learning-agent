"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { useLearnerContext } from "@/components/learner-context";
import { ApiRequestError, type PracticeResponse, apiClient } from "@/lib/api/client";

export default function PracticePage() {
  const params = useParams<{ practiceId: string }>();
  const { cache, isReady } = useLearnerContext();
  const [practice, setPractice] = useState<PracticeResponse | null>(null);
  const [essay, setEssay] = useState("");
  const [error, setError] = useState<string | null>(null);
  const practiceId = Number(params.practiceId);
  const learnerId = cache?.currentLearnerId ?? null;

  useEffect(() => {
    if (!isReady || learnerId === null || !Number.isInteger(practiceId) || practiceId <= 0) return;
    const activeLearnerId: number = learnerId;
    let active = true;
    async function load() {
      try { const value = await apiClient.getPractice(activeLearnerId, practiceId); if (active) setPractice(value); }
      catch (reason) { if (active) setError(reason instanceof ApiRequestError && reason.code === "practice_not_found" ? "未找到这项练习。" : "暂时无法读取练习，请稍后重试。"); }
    }
    void load();
    return () => { active = false; };
  }, [isReady, learnerId, practiceId]);

  if (!isReady) return <p className="status-copy">正在恢复学习进度…</p>;
  if (cache === null) return <section className="content-card narrow-card"><h1>请先设置学习目标</h1><Link className="primary-action" href="/setup">前往学习设置</Link></section>;
  if (!Number.isInteger(practiceId) || practiceId <= 0) return <p className="error-message" role="alert">练习地址无效。</p>;
  if (error !== null) return <p className="error-message" role="alert">{error}</p>;
  if (practice === null) return <p className="status-copy">正在读取练习…</p>;

  return <section className="writing-page"><p className="eyebrow">针对性练习</p><h1>{practice.focus_objective}</h1><article className="content-card"><h2>Writing Task 2</h2><p className="question-copy">{practice.question}</p><h3>写作提示</h3><ul>{practice.instructions.map((item) => <li key={item}>{item}</li>)}</ul><h3>检查清单</h3><ul>{practice.checkpoints.map((item) => <li key={item}>{item}</li>)}</ul></article><section className="content-card next-step"><label htmlFor="practice-essay">你的英文作文</label><textarea id="practice-essay" value={essay} onChange={(event) => setEssay(event.target.value)} /><p className="supporting-copy">作文内容仅保留在当前页面。提交与评估将在下一步提供。</p></section></section>;
}

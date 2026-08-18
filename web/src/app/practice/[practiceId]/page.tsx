"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import { EvaluationDisplay } from "@/components/evaluation-display";
import { useLearnerContext } from "@/components/learner-context";
import { ApiRequestError, type PracticeResponse, type SubmissionResult, type WritingEvaluationResponse, apiClient } from "@/lib/api/client";

export default function PracticePage() {
  const params = useParams<{ practiceId: string }>();
  const { cache, isReady } = useLearnerContext();
  const [practice, setPractice] = useState<PracticeResponse | null>(null);
  const [essay, setEssay] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submission, setSubmission] = useState<SubmissionResult | null>(null);
  const [evaluation, setEvaluation] = useState<WritingEvaluationResponse | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
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
    void load(); return () => { active = false; };
  }, [isReady, learnerId, practiceId]);

  async function submitPractice() {
    if (learnerId === null || essay.trim() === "") return;
    setIsSubmitting(true); setError(null); setEvaluation(null);
    try {
      const result = await apiClient.submitPractice(learnerId, practiceId, essay);
      setSubmission(result);
      if (result.status === "submitted" || result.status === "reused") {
        setEvaluation(await apiClient.getPracticeEvaluation(learnerId, practiceId));
      }
    } catch { setError("暂时无法提交或读取评估，请稍后重试。"); }
    finally { setIsSubmitting(false); }
  }

  if (!isReady) return <p className="status-copy">正在恢复学习进度…</p>;
  if (cache === null) return <section className="content-card narrow-card"><h1>请先设置学习目标</h1><Link className="primary-action" href="/setup">前往学习设置</Link></section>;
  if (!Number.isInteger(practiceId) || practiceId <= 0) return <p className="error-message" role="alert">练习地址无效。</p>;
  if (practice === null) return <p className="status-copy">{error ?? "正在读取练习…"}</p>;

  const statusCopy = submission?.status === "submitted" ? "作文已提交，以下是持久化评估。" : submission?.status === "reused" ? "已复用此前提交的相同作文，以下是持久化评估。" : submission?.status === "conflict" ? "此练习已提交过不同作文，不能覆盖或继续完成。" : submission?.status === "in_progress" ? "提交仍在处理中，请稍后刷新；现在不能继续完成。" : null;
  return <section className="writing-page"><p className="eyebrow">针对性练习</p><h1>{practice.focus_objective}</h1><article className="content-card"><h2>Writing Task 2</h2><p className="question-copy">{practice.question}</p><h3>写作提示</h3><ul>{practice.instructions.map((item) => <li key={item}>{item}</li>)}</ul><h3>检查清单</h3><ul>{practice.checkpoints.map((item) => <li key={item}>{item}</li>)}</ul></article><section className="content-card next-step"><label htmlFor="practice-essay">你的英文作文</label><textarea disabled={submission !== null} id="practice-essay" value={essay} onChange={(event) => setEssay(event.target.value)} />{error !== null && <p className="error-message" role="alert">{error}</p>}{statusCopy !== null && <p className="status-copy">{statusCopy}</p>}{submission === null && <button className="primary-action" disabled={isSubmitting || essay.trim() === ""} onClick={submitPractice} type="button">{isSubmitting ? "正在提交…" : "提交作文并获取评估"}</button>}</section>{evaluation !== null && <EvaluationDisplay evaluation={evaluation.evaluation} />}</section>;
}

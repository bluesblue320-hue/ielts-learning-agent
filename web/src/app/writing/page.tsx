"use client";

import Link from "next/link";
import { useState } from "react";
import { useRouter } from "next/navigation";

import { EvaluationDisplay } from "@/components/evaluation-display";
import { useLearnerContext } from "@/components/learner-context";
import { ApiRequestError, type WritingEvaluationResponse, apiClient } from "@/lib/api/client";

function wordCount(value: string): number { return value.trim() === "" ? 0 : value.trim().split(/\s+/).length; }

export default function WritingPage() {
  const router = useRouter();
  const { cache, isReady, setRecommendation } = useLearnerContext();
  const [question, setQuestion] = useState("");
  const [essay, setEssay] = useState("");
  const [result, setResult] = useState<WritingEvaluationResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isApplying, setIsApplying] = useState(false);

  if (!isReady) return <p className="status-copy">正在恢复学习进度…</p>;
  if (cache === null) return <section className="content-card narrow-card"><h1>请先设置学习目标</h1><Link className="primary-action" href="/setup">前往学习设置</Link></section>;

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setIsSubmitting(true); setError(null); setResult(null);
    try { setResult(await apiClient.evaluateWriting(question, essay)); }
    catch (reason) {
      setError(reason instanceof ApiRequestError && reason.code === "request_invalid" ? "请检查题目和作文内容后重试。" : "写作评估暂时不可用，请稍后重试。");
    } finally { setIsSubmitting(false); }
  }

  async function applyEvaluation() {
    if (result === null || cache === null) return;
    const learnerId = cache.currentLearnerId;
    setIsApplying(true); setError(null);
    try {
      const applied = await apiClient.applyEvaluation(learnerId, result.evaluation_id);
      await apiClient.getLearnerState(learnerId);
      setRecommendation(applied.recommendation_id, applied.recommendation);
      router.push("/dashboard");
    } catch { setError("暂时无法应用学习更新，请稍后重试。"); }
    finally { setIsApplying(false); }
  }
  return <section className="writing-page"><p className="eyebrow">首次写作</p><h1>提交一篇 Writing Task 2 作文</h1><p className="supporting-copy">题目和作文将发送给评估服务；字数仅作本地提示，服务端验证仍为准。</p>
    <form className="stack content-card" onSubmit={submit}>
      <label htmlFor="question">英文 Task 2 题目</label><textarea id="question" required value={question} onChange={(event) => setQuestion(event.target.value)} />
      <label htmlFor="essay">你的英文作文</label><textarea id="essay" required value={essay} onChange={(event) => setEssay(event.target.value)} />
      <p className="supporting-copy">当前字数：{wordCount(essay)}</p>
      {error !== null && <p className="error-message" role="alert">{error}</p>}
      <button className="primary-action" disabled={isSubmitting} type="submit">{isSubmitting ? "正在评估…" : "提交并获取评估"}</button>
    </form>
    {result !== null && <><EvaluationDisplay evaluation={result.evaluation} /><button className="primary-action" disabled={isApplying} onClick={applyEvaluation} type="button">{isApplying ? "正在更新学习状态…" : "应用学习更新"}</button></>}
  </section>;
}

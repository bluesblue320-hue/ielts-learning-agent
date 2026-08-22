"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import {
  type AgentTurnResponse,
  type LearnerStateResponse,
  type WritingContextResponse,
  type WritingGroundedGuidanceResponse,
  type WritingSkill,
  apiClient,
} from "@/lib/api/client";
import { useLearnerContext } from "@/components/learner-context";
import { presentApiError, presentNoPracticeReasons, presentPlanningExplanation, presentPracticeReasons, skillLabels } from "@/lib/presentation";
import { resumeActionExplanations, resumeActionLabels } from "@/lib/memory-presentation";
import { presentAgentStep, presentAgentStopReason } from "@/lib/agent-presentation";

export default function DashboardPage() {
  const router = useRouter();
  const { cache, isReady } = useLearnerContext();
  const [state, setState] = useState<LearnerStateResponse | null>(null);
  const [context, setContext] = useState<WritingContextResponse | null>(null);
  const [guidance, setGuidance] =
    useState<WritingGroundedGuidanceResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [agentTurn, setAgentTurn] = useState<AgentTurnResponse | null>(null);
  const [isAgentBusy, setIsAgentBusy] = useState(false);
  const learnerId = cache?.currentLearnerId ?? null;
  const planningExplanation = presentPlanningExplanation(context?.current_recommendation);

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
      }
    }
    async function loadGuidance() {
      try {
        const result = await apiClient.getWritingGuidance(activeLearnerId);
        if (active) setGuidance(result);
      } catch (reason) {
        if (active) setError(presentApiError(reason));
      }
    }

    async function load() {
      setIsLoading(true);
      setError(null);
      // Load each server-authoritative read model independently so one failure
      // does not blank the other dashboard sections.
      await Promise.all([loadState(), loadContext(), loadGuidance()]);
      if (active) setIsLoading(false);
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

  async function continueWithAgent() {
    if (learnerId === null) return;
    setIsAgentBusy(true); setError(null);
    try { setAgentTurn(await apiClient.agentTurn(learnerId, { turn_type: "continue" })); }
    catch (reason) { setError(presentApiError(reason)); }
    finally { setIsAgentBusy(false); }
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
      {guidance !== null && (
        <section className="content-card next-step" aria-labelledby="ielts-guidance-title">
          <p className="eyebrow">IELTS 官方标准</p>
          <h2 id="ielts-guidance-title">本次写作指导</h2>
          {guidance.current_recommendation === null ? (
            <p className="supporting-copy">完成首次写作后，这里会显示基于官方评分标准的针对性指导。</p>
          ) : guidance.current_recommendation.decision_type === "no_practice" ? (
            <p className="supporting-copy">
              {presentNoPracticeReasons(guidance.current_recommendation.reason_codes)}
            </p>
          ) : (
            <>
              <p className="supporting-copy">
                训练维度：{guidance.current_recommendation.target_skill === null
                  ? "—"
                  : skillLabels[guidance.current_recommendation.target_skill]}
              </p>
              <p className="supporting-copy">
                当前水平：{guidance.current_recommendation.current_estimate ?? "尚未评估"} · 目标：
                {guidance.current_recommendation.learner_target_band?.value ??
                  guidance.learner_state.writing_target_band.value}
              </p>
              <p className="supporting-copy">
                主要差距与下一步：
                {presentPracticeReasons(guidance.current_recommendation.reason_codes)}
              </p>
              {guidance.guidance_items.map((item) => (
                <article key={item.criterion}>
                  <h3>{item.title}</h3>
                  <p className="supporting-copy">IELTS 对该维度的要求：{item.explanation}</p>
                </article>
              ))}
              {guidance.source_citations.length > 0 && (
                <div className="supporting-copy">
                  <p>依据与来源：</p>
                  <ul>
                    {guidance.source_citations.map((citation) => (
                      <li key={`${citation.source_id}-${citation.locator}`}>
                        <a href={citation.url} rel="noreferrer" target="_blank">
                          {citation.publisher}《{citation.title}》
                        </a>
                        （{citation.locator}）
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          )}
        </section>
      )}
      <section className="content-card next-step">
        <h2>继续学习</h2>
        <button className="secondary-action" disabled={isAgentBusy} onClick={continueWithAgent} type="button">{isAgentBusy ? "正在继续学习…" : "使用学习助手继续"}</button>
        {agentTurn !== null && (
          <div className="supporting-copy" aria-live="polite" role="status">
            <p>学习助手状态：{presentAgentStopReason(agentTurn.stop_reason)}</p>
            <ol>
              {agentTurn.steps.map((step, index) => (
                <li key={`${index}-${step.tool}-${step.outcome}`}>
                  {presentAgentStep(step.tool, step.outcome)}
                </li>
              ))}
                        </ol>
            {agentTurn.current_practice !== null && (
              <Link className="primary-action" href={`/practice/${agentTurn.current_practice.id}`}>
                开始本次练习
              </Link>
            )}
          </div>
        )}
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
        {planningExplanation !== null && (
          <p className="supporting-copy" role="status">
            推荐依据：{planningExplanation}
          </p>
        )}
      </section>
      <p className="supporting-copy nav-hint">
        <Link href="/history">查看写作历史</Link> · <Link href="/progress">查看学习进度</Link>
      </p>
    </section>
  );
}

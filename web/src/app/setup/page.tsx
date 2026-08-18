"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { ApiRequestError, apiClient } from "@/lib/api/client";
import { useLearnerContext } from "@/components/learner-context";

const targetBands = ["5.5", "6.0", "6.5", "7.0", "7.5", "8.0"];

export default function SetupPage() {
  const router = useRouter();
  const { setLearner } = useLearnerContext();
  const [targetBand, setTargetBand] = useState("7.0");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsSubmitting(true);
    setError(null);
    try {
      const learner = await apiClient.createLearner(targetBand);
      setLearner(learner.id, learner.writing_target_band.value);
      router.push("/writing");
    } catch (reason) {
      setError(
        reason instanceof ApiRequestError && reason.code === "request_invalid"
          ? "请选择有效的目标分数。"
          : "暂时无法保存学习设置，请稍后重试。",
      );
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <section className="content-card narrow-card">
      <p className="eyebrow">学习设置</p>
      <h1>你的 Writing 目标分数是？</h1>
      <p className="supporting-copy">这会由服务端保存，并作为后续练习建议的依据。</p>
      <form className="stack" onSubmit={submit}>
        <label htmlFor="target-band">目标分数</label>
        <select
          id="target-band"
          value={targetBand}
          onChange={(event) => setTargetBand(event.target.value)}
        >
          {targetBands.map((band) => <option key={band} value={band}>{band}</option>)}
        </select>
        {error !== null && <p className="error-message" role="alert">{error}</p>}
        <button className="primary-action" disabled={isSubmitting} type="submit">
          {isSubmitting ? "正在保存…" : "开始首次写作"}
        </button>
      </form>
    </section>
  );
}

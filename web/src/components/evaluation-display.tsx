import type { WritingEvaluation } from "@/lib/api/client";

const labels = {
  task_response: "任务回应（Task Response）",
  coherence_and_cohesion: "连贯与衔接（Coherence and Cohesion）",
  lexical_resource: "词汇资源（Lexical Resource）",
  grammatical_range_and_accuracy: "语法多样性与准确性（Grammatical Range and Accuracy）",
} as const;

export function EvaluationDisplay({ evaluation }: { evaluation: WritingEvaluation }) {
  return (
    <section className="evaluation" aria-labelledby="evaluation-title">
      <p className="eyebrow">写作评估</p>
      <h2 id="evaluation-title">综合分数：{evaluation.product_band.value}</h2>
      <p className="supporting-copy">{evaluation.feedback}</p>
      <div className="state-grid">
        {Object.entries(labels).map(([key, label]) => {
          const criterion = evaluation.criteria[key as keyof typeof labels];
          return <article className="content-card" key={key}><h3>{label}</h3><p className="metric">{criterion.band.value}</p><p>{criterion.feedback}</p></article>;
        })}
      </div>
      <h3>优势</h3><ul>{evaluation.strengths.map((item) => <li key={item}>{item}</li>)}</ul>
      <h3>下一步可改进之处</h3><ul>{evaluation.weaknesses.map((item) => <li key={item}>{item}</li>)}</ul>
    </section>
  );
}

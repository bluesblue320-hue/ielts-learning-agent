import Link from "next/link";

export default function Home() {
  return (
    <section className="hero">
      <p className="eyebrow">Writing MVP</p>
      <h1>把每一次写作练习，接入可追踪的学习闭环。</h1>
      <p>
        设置目标分数，提交一篇 Task 2 写作，然后按照系统返回的学习状态和练习建议继续。
      </p>
      <Link className="primary-action" href="/setup">开始设置</Link>
    </section>
  );
}

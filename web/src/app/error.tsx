"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return <section className="content-card narrow-card"><h1>页面暂时无法继续</h1><p className="supporting-copy">请重试；如果问题持续出现，可以刷新页面后再次操作。</p><button className="primary-action" onClick={reset} type="button">重试</button></section>;
}
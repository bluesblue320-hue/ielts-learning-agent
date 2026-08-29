"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useLearnerContext } from "@/components/learner-context";

const navigation = [
  { href: "/dashboard", label: "学习概览" },
  { href: "/writing", label: "首次写作" },
  { href: "/history", label: "历史" },
  { href: "/progress", label: "进度" },
  { href: "/knowledge", label: "知识库" },
  { href: "/setup", label: "学习设置" },
];

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { cache, isReady } = useLearnerContext();

  return (
    <div className="app-shell">
      <header className="site-header">
        <Link className="brand" href="/">IELTS 学习助手</Link>
        <nav aria-label="主要导航">
          {navigation.map((item) => (
            <Link
              aria-current={pathname === item.href || pathname.startsWith(`${item.href}/`) ? "page" : undefined}
              className={pathname === item.href || pathname.startsWith(`${item.href}/`) ? "nav-link active" : "nav-link"}
              href={item.href}
              key={item.href}
            >
              {item.label}
            </Link>
          ))}
        </nav>
        <p className="learner-status" aria-live="polite">
          {!isReady ? "正在恢复学习进度…" : cache === null ? "尚未设置学习者" : `目标：${cache.writingTargetBand}`}
        </p>
      </header>
      <main className="page-content">{children}</main>
    </div>
  );
}

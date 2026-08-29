"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import {
  apiClient,
  type WikiIndexResponse,
  type WikiPageSummary,
} from "@/lib/api/client";
import { presentApiError } from "@/lib/presentation";
import { wikiPageTypeLabels } from "@/lib/wiki-presentation";

function WikiTreeItem({
  page,
  childrenByParent,
}: {
  page: WikiPageSummary;
  childrenByParent: Map<string, WikiPageSummary[]>;
}) {
  const children = childrenByParent.get(page.page_id) ?? [];
  return (
    <li className={`wiki-tree-item wiki-tree-${page.page_type}`}>
      <Link className="wiki-page-link" href={`/knowledge/${page.page_id}`}>
        <span>{page.title}</span>
        <span className="wiki-page-kind">{wikiPageTypeLabels[page.page_type]}</span>
      </Link>
      {children.length > 0 && (
        <ul className="wiki-tree-children">
          {children.map((child) => (
            <WikiTreeItem
              childrenByParent={childrenByParent}
              key={child.page_id}
              page={child}
            />
          ))}
        </ul>
      )}
    </li>
  );
}

export default function KnowledgeIndexPage() {
  const [index, setIndex] = useState<WikiIndexResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      setIndex(await apiClient.getWikiIndex());
    } catch (reason) {
      setError(presentApiError(reason));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    async function loadIndex() {
      try {
        const result = await apiClient.getWikiIndex();
        if (active) setIndex(result);
      } catch (reason) {
        if (active) setError(presentApiError(reason));
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadIndex();
    return () => { active = false; };
  }, []);

  const childrenByParent = new Map<string, WikiPageSummary[]>();
  for (const page of index?.pages ?? []) {
    if (page.parent_page_id === null) continue;
    const siblings = childrenByParent.get(page.parent_page_id) ?? [];
    siblings.push(page);
    childrenByParent.set(page.parent_page_id, siblings);
  }
  const root = index?.pages.find((page) => page.page_id === index.root_page_id) ?? null;

  return (
    <section className="wiki-page">
      <p className="eyebrow">IELTS 写作知识库</p>
      <h1>Writing Task 2 知识导航</h1>
      <p className="supporting-copy">
        按评分维度、分数档、写作规则和题型浏览经过来源核验的 IELTS Writing Task 2 知识。
      </p>
      {isLoading && <p className="status-copy" aria-live="polite">正在读取知识目录…</p>}
      {error !== null && (
        <div role="alert">
          <p className="error-message">{error}</p>
          <button className="retry-action" onClick={() => void load()} type="button">重试</button>
        </div>
      )}
      {!isLoading && error === null && root === null && (
        <p className="supporting-copy">当前没有可浏览的知识页面。</p>
      )}
      {root !== null && (
        <nav aria-label="Writing Task 2 知识目录" className="wiki-tree content-card">
          <ul className="wiki-tree-root">
            <WikiTreeItem childrenByParent={childrenByParent} page={root} />
          </ul>
        </nav>
      )}
    </section>
  );
}

"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useState } from "react";

import { apiClient, type WikiPageDetail } from "@/lib/api/client";
import { presentApiError } from "@/lib/presentation";
import {
  wikiKnowledgeMetadata,
  wikiNeighborLabels,
  wikiPageTypeLabels,
  wikiSourceLocation,
} from "@/lib/wiki-presentation";

export default function KnowledgeDetailPage() {
  const { pageId } = useParams<{ pageId: string }>();
  const [detail, setDetail] = useState<WikiPageDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  async function load() {
    setIsLoading(true);
    setError(null);
    try {
      setDetail(await apiClient.getWikiPage(pageId));
    } catch (reason) {
      setDetail(null);
      setError(presentApiError(reason));
    } finally {
      setIsLoading(false);
    }
  }

  useEffect(() => {
    let active = true;
    async function loadDetail() {
      try {
        const result = await apiClient.getWikiPage(pageId);
        if (active) setDetail(result);
      } catch (reason) {
        if (active) {
          setDetail(null);
          setError(presentApiError(reason));
        }
      } finally {
        if (active) setIsLoading(false);
      }
    }
    void loadDetail();
    return () => { active = false; };
  }, [pageId]);

  if (isLoading) {
    return <p className="status-copy" aria-live="polite">正在读取知识页面…</p>;
  }
  if (error !== null || detail === null) {
    return (
      <section className="content-card narrow-card">
        <h1>知识页面暂时无法显示</h1>
        <p className="error-message" role="alert">{error ?? "未找到这个知识页面。"}</p>
        <button className="retry-action" onClick={() => void load()} type="button">重试</button>
        <p className="back-link"><Link href="/knowledge">返回知识目录</Link></p>
      </section>
    );
  }

  const bandNeighbors = detail.neighbors.filter(
    (neighbor) => neighbor.direction === "previous_band" || neighbor.direction === "next_band",
  );
  const hierarchyNeighbors = detail.neighbors.filter(
    (neighbor) => neighbor.direction === "parent" || neighbor.direction === "child",
  );

  return (
    <article className="wiki-page">
      <nav aria-label="知识页路径" className="wiki-breadcrumbs">
        <ol>
          {detail.breadcrumbs.map((crumb, index) => (
            <li key={crumb.page_id}>
              {index < detail.breadcrumbs.length - 1 ? (
                <Link href={`/knowledge/${crumb.page_id}`}>{crumb.title}</Link>
              ) : (
                <span aria-current="page">{crumb.title}</span>
              )}
            </li>
          ))}
        </ol>
      </nav>
      <p className="eyebrow">{wikiPageTypeLabels[detail.page.page_type]}</p>
      <h1>{detail.page.title}</h1>

      {detail.knowledge.length === 0 && (
        <p className="supporting-copy">此页面用于组织下方知识分类，本页没有独立的 IELTS 事实陈述。</p>
      )}
      {detail.knowledge.map((knowledge) => (
        <section className="content-card wiki-knowledge" key={knowledge.knowledge_id}>
          <h2>官方知识内容</h2>
          <p className="wiki-statement">{knowledge.statement}</p>
          {wikiKnowledgeMetadata(knowledge).length > 0 && (
            <ul className="wiki-metadata">
              {wikiKnowledgeMetadata(knowledge).map((item) => <li key={item}>{item}</li>)}
            </ul>
          )}
          <div className="wiki-sources">
            <h3>依据与来源</h3>
            <ul>
              {knowledge.sources.map((source) => (
                <li key={`${source.source_id}-${source.locator}-${source.page ?? ""}-${source.section ?? ""}`}>
                  <a href={source.url} rel="noreferrer" target="_blank">
                    {source.publisher}《{source.title}》
                  </a>
                  <span>{wikiSourceLocation(source)}</span>
                </li>
              ))}
            </ul>
          </div>
        </section>
      ))}

      {detail.children.length > 0 && (
        <nav aria-label="下级知识页面" className="content-card wiki-section">
          <h2>继续浏览</h2>
          <ul className="wiki-link-list">
            {detail.children.map((child) => (
              <li key={child.page_id}><Link href={`/knowledge/${child.page_id}`}>{child.title}</Link></li>
            ))}
          </ul>
        </nav>
      )}

      {bandNeighbors.length > 0 && (
        <nav aria-label="相邻分数档描述" className="content-card wiki-section">
          <h2>相邻评分描述</h2>
          <p className="supporting-copy">以下链接仅表示数字上相邻的描述档位，不代表推荐学习顺序。</p>
          <ul className="wiki-link-list">
            {bandNeighbors.map((neighbor) => (
              <li key={`${neighbor.direction}-${neighbor.page_id}`}>
                <Link href={`/knowledge/${neighbor.page_id}`}>
                  {wikiNeighborLabels[neighbor.direction]}：{neighbor.title}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      )}

      {hierarchyNeighbors.some((neighbor) => neighbor.direction === "parent") && (
        <p className="back-link">
          {hierarchyNeighbors.filter((neighbor) => neighbor.direction === "parent").map((neighbor) => (
            <Link href={`/knowledge/${neighbor.page_id}`} key={neighbor.page_id}>
              {wikiNeighborLabels.parent}：{neighbor.title}
            </Link>
          ))}
        </p>
      )}
    </article>
  );
}

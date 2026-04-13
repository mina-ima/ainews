import fs from "fs";
import path from "path";

export interface ArticleMeta {
  date: string;
  title: string;
  article_count: number;
  audio_url: string;
  audio_size_mb: number;
}

export interface IndexData {
  articles: ArticleMeta[];
}

const REPO = "mina-ima/ainews";
const BRANCH = "main";
const RAW_BASE = `https://raw.githubusercontent.com/${REPO}/${BRANCH}/articles`;

// ローカル開発時はファイルシステムから、Vercel上はGitHubから取得
const ARTICLES_DIR = path.join(process.cwd(), "..", "articles");
const isLocal = fs.existsSync(ARTICLES_DIR);

export async function getIndex(): Promise<IndexData> {
  if (isLocal) {
    const indexPath = path.join(ARTICLES_DIR, "index.json");
    if (!fs.existsSync(indexPath)) return { articles: [] };
    return JSON.parse(fs.readFileSync(indexPath, "utf-8"));
  }
  // Vercel: GitHubから取得
  const res = await fetch(`${RAW_BASE}/index.json`, { next: { revalidate: 300 } });
  if (!res.ok) return { articles: [] };
  return res.json();
}

export async function getArticleContent(date: string): Promise<string | null> {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) return null;

  if (isLocal) {
    const mdPath = path.join(ARTICLES_DIR, `${date}.md`);
    if (!fs.existsSync(mdPath)) return null;
    const content = fs.readFileSync(mdPath, "utf-8");
    const match = content.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/);
    return match ? match[1].trim() : content;
  }
  // Vercel: GitHubから取得
  const res = await fetch(`${RAW_BASE}/${date}.md`, { next: { revalidate: 300 } });
  if (!res.ok) return null;
  const content = await res.text();
  const match = content.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/);
  return match ? match[1].trim() : content;
}

export async function getArticleDates(): Promise<string[]> {
  const { articles } = await getIndex();
  return articles.map((a) => a.date);
}

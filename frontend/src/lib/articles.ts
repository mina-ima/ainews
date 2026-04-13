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

const ARTICLES_DIR = path.join(process.cwd(), "..", "articles");

export function getIndex(): IndexData {
  const indexPath = path.join(ARTICLES_DIR, "index.json");
  if (!fs.existsSync(indexPath)) {
    return { articles: [] };
  }
  return JSON.parse(fs.readFileSync(indexPath, "utf-8"));
}

export function getArticleContent(date: string): string | null {
  const mdPath = path.join(ARTICLES_DIR, `${date}.md`);
  if (!fs.existsSync(mdPath)) {
    return null;
  }
  const content = fs.readFileSync(mdPath, "utf-8");
  // frontmatter を除去
  const match = content.match(/^---\n[\s\S]*?\n---\n([\s\S]*)$/);
  return match ? match[1].trim() : content;
}

export function getArticleDates(): string[] {
  const { articles } = getIndex();
  return articles.map((a) => a.date);
}

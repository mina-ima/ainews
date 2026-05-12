import { getIndex } from "@/lib/articles";
import ArticleCard from "@/components/ArticleCard";

export const dynamic = "force-dynamic";

export default async function Home() {
  const { articles } = await getIndex();

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">最新ニュース</h1>

      {articles.length === 0 ? (
        <p className="text-slate-400">まだ記事がありません。</p>
      ) : (
        <div className="space-y-3">
          {articles.map((article) => (
            <ArticleCard key={article.date} article={article} />
          ))}
        </div>
      )}
    </div>
  );
}

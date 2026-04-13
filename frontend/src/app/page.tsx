import Link from "next/link";
import { getIndex } from "@/lib/articles";

export default function Home() {
  const { articles } = getIndex();

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-6">最新ニュース</h1>

      {articles.length === 0 ? (
        <p className="text-slate-400">まだ記事がありません。</p>
      ) : (
        <div className="space-y-3">
          {articles.map((article) => (
            <Link
              key={article.date}
              href={`/articles/${article.date}`}
              className="block p-4 rounded-lg bg-slate-900 border border-slate-800 hover:border-blue-500 transition-colors"
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm text-slate-400">{article.date}</p>
                  <p className="font-medium mt-1">{article.title}</p>
                  <p className="text-sm text-slate-500 mt-1">
                    {article.article_count}件のトピック
                    {article.audio_size_mb > 0 &&
                      ` / 音声 ${article.audio_size_mb}MB`}
                  </p>
                </div>
                <span className="text-slate-600">→</span>
              </div>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

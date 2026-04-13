import Link from "next/link";
import { getIndex } from "@/lib/articles";

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
            <div
              key={article.date}
              className="p-4 rounded-lg bg-slate-900 border border-slate-800"
            >
              <Link
                href={`/articles/${article.date}`}
                className="block hover:text-blue-400 transition-colors"
              >
                <p className="text-sm text-slate-400">{article.date}</p>
                <p className="font-medium mt-1">{article.title}</p>
                <p className="text-sm text-slate-500 mt-1">
                  {article.article_count}件のトピック
                </p>
              </Link>
              <div className="flex gap-3 mt-3">
                <Link
                  href={`/articles/${article.date}`}
                  className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-sm text-white"
                >
                  記事を読む
                </Link>
                {article.audio_url && (
                  <a
                    href={article.audio_url}
                    download
                    className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm text-slate-200"
                  >
                    MP3ダウンロード ({article.audio_size_mb}MB)
                  </a>
                )}
                <a
                  href={`/api/download/${article.date}`}
                  className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm text-slate-200"
                >
                  MDダウンロード
                </a>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

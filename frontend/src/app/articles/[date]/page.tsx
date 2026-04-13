import Link from "next/link";
import { notFound } from "next/navigation";
import { getIndex, getArticleContent, getArticleDates } from "@/lib/articles";
import AudioPlayer from "@/components/AudioPlayer";
import MarkdownView from "@/components/MarkdownView";

export async function generateStaticParams() {
  return getArticleDates().map((date) => ({ date }));
}

export default async function ArticlePage({
  params,
}: {
  params: Promise<{ date: string }>;
}) {
  const { date } = await params;
  const content = getArticleContent(date);
  if (!content) notFound();

  const { articles } = getIndex();
  const meta = articles.find((a) => a.date === date);

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <Link
        href="/"
        className="text-sm text-slate-400 hover:text-slate-300 mb-4 inline-block"
      >
        ← 一覧に戻る
      </Link>

      {meta?.audio_url && <AudioPlayer src={meta.audio_url} />}

      <article className="mt-6">
        <MarkdownView content={content} />
      </article>

      <div className="mt-8 flex gap-4 text-sm">
        <a
          href={`/api/download/${date}`}
          className="px-4 py-2 rounded bg-slate-800 hover:bg-slate-700 text-slate-300"
        >
          Markdownをダウンロード
        </a>
      </div>
    </div>
  );
}

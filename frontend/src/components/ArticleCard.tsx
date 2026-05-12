"use client";

import { useState } from "react";
import Link from "next/link";
import AudioPlayer from "./AudioPlayer";
import type { ArticleMeta } from "@/lib/articles";

export default function ArticleCard({ article }: { article: ArticleMeta }) {
  const [showPlayer, setShowPlayer] = useState(false);
  const audioSrc = `/api/audio/${article.date}`;

  return (
    <div className="p-4 rounded-lg bg-slate-900 border border-slate-800">
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

      {showPlayer && (
        <div className="mt-3">
          <AudioPlayer src={audioSrc} />
        </div>
      )}

      <div className="flex flex-wrap gap-2 mt-3">
        <Link
          href={`/articles/${article.date}`}
          className="px-3 py-1.5 rounded bg-blue-600 hover:bg-blue-500 text-sm text-white"
        >
          記事を読む
        </Link>
        {article.audio_url && (
          <button
            onClick={() => setShowPlayer((v) => !v)}
            className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm text-slate-200"
          >
            {showPlayer ? "⏹ プレーヤーを閉じる" : "▶ 再生"}
          </button>
        )}
        <a
          href={`/api/download/${article.date}`}
          className="px-3 py-1.5 rounded bg-slate-700 hover:bg-slate-600 text-sm text-slate-200"
        >
          MDダウンロード
        </a>
      </div>
    </div>
  );
}

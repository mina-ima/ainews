"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

export default function MarkdownView({ content }: { content: string }) {
  return (
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        h1: ({ children }) => (
          <h1 className="text-2xl font-bold mt-6 mb-3">{children}</h1>
        ),
        h2: ({ children }) => (
          <h2 className="text-xl font-semibold mt-6 mb-2 text-blue-400">
            {children}
          </h2>
        ),
        h3: ({ children }) => (
          <h3 className="text-lg font-medium mt-4 mb-2">{children}</h3>
        ),
        p: ({ children }) => (
          <p className="text-slate-300 leading-relaxed mb-3">{children}</p>
        ),
        a: ({ href, children }) => (
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-400 hover:text-blue-300 underline"
          >
            {children}
          </a>
        ),
        hr: () => <hr className="border-slate-700 my-4" />,
        ul: ({ children }) => (
          <ul className="list-disc pl-5 mb-3 text-slate-300">{children}</ul>
        ),
        li: ({ children }) => <li className="mb-1">{children}</li>,
        strong: ({ children }) => (
          <strong className="text-slate-100 font-semibold">{children}</strong>
        ),
        em: ({ children }) => (
          <em className="text-slate-400 italic">{children}</em>
        ),
      }}
    >
      {content}
    </ReactMarkdown>
  );
}

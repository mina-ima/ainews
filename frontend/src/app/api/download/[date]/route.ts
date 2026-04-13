import { NextResponse } from "next/server";
import { getArticleContent } from "@/lib/articles";

export async function GET(
  _request: Request,
  { params }: { params: Promise<{ date: string }> }
) {
  const { date } = await params;

  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: "Invalid date" }, { status: 400 });
  }

  const content = await getArticleContent(date);
  if (!content) {
    return NextResponse.json({ error: "Not found" }, { status: 404 });
  }

  return new NextResponse(content, {
    headers: {
      "Content-Type": "text/markdown; charset=utf-8",
      "Content-Disposition": `attachment; filename="ainews-${date}.md"`,
    },
  });
}

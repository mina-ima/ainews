import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";

const ARTICLES_DIR = path.join(process.cwd(), "..", "articles");
const REPO = "mina-ima/ainews";

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  const { date } = await params;

  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: "Invalid date" }, { status: 400 });
  }

  const rangeHeader = request.headers.get("range");

  // ローカルに MP3 があればそれを配信。無ければ GitHub Releases へ委譲する
  const mp3Path = path.join(ARTICLES_DIR, `${date}.mp3`);
  if (fs.existsSync(mp3Path)) {
    const stat = fs.statSync(mp3Path);
    const fileSize = stat.size;

    if (rangeHeader) {
      const [, rangeStr] = rangeHeader.split("=");
      const [startStr, endStr] = rangeStr.split("-");
      const start = parseInt(startStr, 10);
      const end = endStr ? parseInt(endStr, 10) : fileSize - 1;
      const chunkSize = end - start + 1;

      const stream = fs.createReadStream(mp3Path, { start, end });
      const body = new ReadableStream({
        start(controller) {
          stream.on("data", (chunk) => controller.enqueue(chunk));
          stream.on("end", () => controller.close());
          stream.on("error", (err) => controller.error(err));
        },
      });

      return new NextResponse(body, {
        status: 206,
        headers: {
          "Content-Range": `bytes ${start}-${end}/${fileSize}`,
          "Accept-Ranges": "bytes",
          "Content-Length": String(chunkSize),
          "Content-Type": "audio/mpeg",
        },
      });
    }

    const buffer = fs.readFileSync(mp3Path);
    return new NextResponse(buffer, {
      headers: {
        "Content-Type": "audio/mpeg",
        "Content-Length": String(fileSize),
        "Accept-Ranges": "bytes",
      },
    });
  }

  // Vercel: GitHub Releases へリダイレクト（Range 処理も帯域も GitHub 側に任せる。
  // プロキシすると Vercel のレスポンス上限 4.5MB に MP3 が引っかかる）
  return NextResponse.redirect(
    `https://github.com/${REPO}/releases/download/news-${date}/${date}.mp3`,
    302
  );
}

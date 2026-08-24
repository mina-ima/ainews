import { NextRequest, NextResponse } from "next/server";
import fs from "fs";
import path from "path";
import { Readable } from "stream";

const ARTICLES_DIR = path.join(process.cwd(), "..", "articles");
const REPO = "mina-ima/ainews";

// Node stream → Web stream。手書きのアダプタと違い backpressure と
// cancel（クライアント切断）が伝播するので、放置された接続がFDを掴み続けない
function toWebStream(nodeStream: fs.ReadStream): ReadableStream<Uint8Array> {
  return Readable.toWeb(nodeStream) as ReadableStream<Uint8Array>;
}

export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ date: string }> }
) {
  const { date } = await params;

  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    return NextResponse.json({ error: "Invalid date" }, { status: 400 });
  }

  const mp3Path = path.join(ARTICLES_DIR, `${date}.mp3`);
  if (!fs.existsSync(mp3Path)) {
    // Vercel: GitHub Releases へリダイレクト（Range 処理も帯域も GitHub 側に任せる。
    // プロキシすると Vercel のレスポンス上限 4.5MB に MP3 が引っかかる）
    return NextResponse.redirect(
      `https://github.com/${REPO}/releases/download/news-${date}/${date}.mp3`,
      302
    );
  }

  const fileSize = fs.statSync(mp3Path).size;
  const rangeHeader = request.headers.get("range");

  if (!rangeHeader) {
    return new NextResponse(toWebStream(fs.createReadStream(mp3Path)), {
      headers: {
        "Content-Type": "audio/mpeg",
        "Content-Length": String(fileSize),
        "Accept-Ranges": "bytes",
      },
    });
  }

  const unsatisfiable = () =>
    new NextResponse(null, {
      status: 416,
      headers: { "Content-Range": `bytes */${fileSize}`, "Accept-Ranges": "bytes" },
    });

  // bytes=START-END / bytes=START- / bytes=-SUFFIX のみ受け付ける。
  // 複数レンジや単位違いは 416（不正値で NaN のまま createReadStream に渡すと 500 になる）
  const match = /^bytes=(\d*)-(\d*)$/.exec(rangeHeader.trim());
  if (!match) return unsatisfiable();

  const [, startStr, endStr] = match;
  let start: number;
  let end: number;

  if (startStr === "") {
    // suffix range: 末尾 N バイト
    const suffix = Number(endStr);
    if (endStr === "" || suffix === 0) return unsatisfiable();
    start = Math.max(0, fileSize - suffix);
    end = fileSize - 1;
  } else {
    start = Number(startStr);
    end = endStr === "" ? fileSize - 1 : Math.min(Number(endStr), fileSize - 1);
  }

  if (start > end || start >= fileSize) return unsatisfiable();

  return new NextResponse(
    toWebStream(fs.createReadStream(mp3Path, { start, end })),
    {
      status: 206,
      headers: {
        "Content-Range": `bytes ${start}-${end}/${fileSize}`,
        "Accept-Ranges": "bytes",
        "Content-Length": String(end - start + 1),
        "Content-Type": "audio/mpeg",
      },
    }
  );
}

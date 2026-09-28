// GitHub の schedule は丸ごとドロップする日がある（2026-09-29 は cron 4本とも不発）。
// Cloudflare の cron は定刻に動くので、当日分が無ければここから workflow_dispatch をかける。
// 秘密: GITHUB_TOKEN（fine-grained PAT / mina-ima/ainews / Contents: Read, Actions: Read and write）
const REPO = "mina-ima/ainews";
const WORKFLOW = "collect.yml";

export default {
  async scheduled(_event, env) {
    const gh = (path, init = {}) =>
      fetch(`https://api.github.com/repos/${REPO}${path}`, {
        ...init,
        headers: {
          Authorization: `Bearer ${env.GITHUB_TOKEN}`,
          Accept: "application/vnd.github+json",
          "User-Agent": "ainews-watchdog",
        },
      });

    const date = new Date(Date.now() + 9 * 3600e3).toISOString().slice(0, 10); // JST
    if ((await gh(`/contents/articles/${date}.md`)).ok) return console.log(`${date}: 生成済み`);

    // 遅れて来た schedule が走っている最中なら任せる（dispatch は guard を素通りして上書きするため）
    const { workflow_runs = [] } = await (await gh(`/actions/workflows/${WORKFLOW}/runs?per_page=5`)).json();
    if (workflow_runs.some((r) => r.status !== "completed")) return console.log(`${date}: 実行中`);

    const res = await gh(`/actions/workflows/${WORKFLOW}/dispatches`, {
      method: "POST",
      body: JSON.stringify({ ref: "main" }),
    });
    if (!res.ok) throw new Error(`dispatch 失敗 ${res.status}: ${await res.text()}`);
    console.log(`${date}: 未生成のため workflow_dispatch を実行`);
  },
};

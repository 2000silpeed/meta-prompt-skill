#!/usr/bin/env python3
"""canvas/ 실험 결과로 블라인드 비교 페이지(canvas/site/)를 만든다. 스타일·스크립트는 site/index.html과 같다."""
import html, json, re, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE / "canvas"
SITE = EXP / "site"
BASE = (HERE / "site/index.html").read_text()
STYLE = re.search(r"<style>.*?</style>", BASE, re.S).group(0)
SCRIPT = re.search(r"<script>.*?</script>", BASE, re.S).group(0)

ORDER = [("A", "skill"), ("B", "noskill"), ("C", "raw")]  # 블라인드 순서 고정(무작위로 정함)
LABEL = {"raw": "원래 요청 그대로", "skill": "meta-prompt 스킬(짧은 프롬프트 + 추가 질문)", "noskill": "스킬 없이 만든 프롬프트"}
NOTES = json.loads((EXP / "notes.json").read_text()) if (EXP / "notes.json").exists() else {}


def main(takes=2):
    P = json.loads((EXP / "prompts.json").read_text())
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir(parents=True)
    secs = []
    for L, c in ORDER:
        figs = []
        for k in range(1, takes + 1):
            src = EXP / "renders" / f"{c}-{k}" / "video.mp4"
            name = f"{L.lower()}{k}"
            if src.exists():
                shutil.copy(src, SITE / f"{name}.mp4")
                subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", "9.2", "-i", str(src), "-frames:v", "1",
                                "-vf", "scale=-2:360", str(SITE / f"{name}.jpg")], check=True)
                h = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
                                        "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip().split(",")[1])
                w = int(subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width",
                                        "-of", "csv=p=0", str(src)], capture_output=True, text=True).stdout.strip())
                tall = " tall" if h > w else ""
                figs.append(f'<figure class="take{tall}"><video id="v-{name}" src="{name}.mp4" poster="{name}.jpg" controls muted loop playsinline preload="metadata"></video><figcaption>테이크 {k}</figcaption></figure>')
            else:
                figs.append(f'<figure class="take"><div class="failbox">테이크 {k}는 렌더링에 실패했습니다.</div><figcaption>테이크 {k}</figcaption></figure>')
        gen_cost = P[c].get("cost_usd") or 0
        r_cost = [json.loads((EXP / "renders" / f"{c}-{k}" / "generator.json").read_text()).get("cost_usd") or 0 for k in range(1, takes + 1)]
        shown = P[c].get("response") or P[c]["prompt"]
        secs.append(f'''<section class="cond" data-cond="{L.lower()}">
<header class="cond-head"><span class="letter">{L}</span><div class="who"><span class="blind-name">조건 {L}</span><span class="real-name" hidden>{LABEL[c]}</span></div><span class="len" hidden>프롬프트 {len(P[c]['prompt']):,}자</span></header>
<div class="takes">{"".join(figs)}</div>
<div class="reveal-body" hidden>
<p class="note">{html.escape(NOTES.get(c, ""))}</p>
<details><summary>{"사용자가 받은 답 그대로 보기" if c != "raw" else "실행자에게 준 요청 보기"}</summary><pre>{html.escape(shown)}</pre></details>
<p class="meta">프롬프트 생성 ${gen_cost:.2f} · 영상 코드 생성 평균 ${sum(r_cost) / len(r_cost):.2f}</p>
</div></section>''')
    page = f'''<title>딸기라떼 Canvas 광고 시사</title>
<meta name="claude:viewport-fit-sides" content="cover">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Do+Hyeon&family=IBM+Plex+Sans+KR:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
{STYLE}
<style>.failbox{{aspect-ratio:16/9;max-width:100%;display:grid;place-items:center;padding:16px;text-align:center;border:1px dashed var(--rule);border-radius:6px;color:var(--muted);font-size:13.5px;background:var(--well)}}</style>
<div class="wrap">
<header style="display:grid;gap:12px">
<h1>딸기라떼 10초 광고, Canvas로 만들기</h1>
<p class="lede">이번에는 처음부터 "Claude가 HTML Canvas 애니메이션으로 만들 광고"용 프롬프트를 조건별로 만들었습니다. 같은 실행자가 각 프롬프트로 영상을 두 번씩 만들었습니다. 먼저 이름을 가린 채로 보고 마음에 드는 조건을 고른 뒤 공개해 보세요.</p>
<div class="req"><span class="k">사용자 요청</span><q>{html.escape(P["request"])}</q></div>
<ul class="setup" aria-label="고정 조건">
<li>실행자: 스킬 없는 새 Claude 세션</li>
<li>10초 · 24fps · 소리 없음</li>
<li>모든 조건에 같은 제출 형식 안내를 덧붙임</li>
</ul>
</header>
<div class="bar"><p id="status">조건 이름이 가려져 있습니다. A·B·C 순서는 무작위입니다.</p><button id="playall" class="ghost" type="button">전체 재생</button><button id="reveal" type="button">조건 공개</button></div>
{chr(10).join(secs)}
<section class="caveats">
<h2>이 비교에서 볼 수 없는 것</h2>
<ul>
<li>조건별 두 테이크뿐이고, 같은 프롬프트라도 테이크마다 결과가 꽤 다릅니다.</li>
<li>모든 프롬프트 뒤에 캡처용 제출 형식(파일 하나, 1280x720 기본, 프레임을 그리는 함수)을 같은 문장으로 붙였습니다. 프롬프트가 세로 화면 같은 다른 형식을 요구하면 그 요구를 따랐습니다.</li>
<li>프롬프트가 요구한 녹화·다시 보기 버튼은 캔버스 밖 요소라 영상에는 나오지 않습니다.</li>
</ul>
</section>
</div>
{SCRIPT}'''
    (SITE / "index.html").write_text(page)
    print("built", [p.name for p in sorted(SITE.iterdir())])


if __name__ == "__main__":
    main()

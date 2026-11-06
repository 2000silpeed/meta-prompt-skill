#!/usr/bin/env python3
"""영상 프롬프트 → 자체 렌더링(코드 애니메이션) → mp4.

실제 영상 생성 모델 대신, 스킬 없는 새 Claude 세션이 '영상 생성기' 역할로 각 프롬프트를
10초 HTML Canvas 애니메이션으로 만든다. 모든 조건에 같은 지시(GENERATOR)를 주고 프롬프트만 바꾼다.
그 다음 headless Chromium으로 프레임을 하나씩 찍어 ffmpeg로 mp4를 만든다.

usage: render.py [--takes 2] [--only raw skill noskill]
"""
import argparse, concurrent.futures as cf, json, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
import e2e  # claude()

HERE = Path(__file__).resolve().parent
OUT = HERE / "renders"
FPS, SECONDS = 24, 10

GENERATOR = """너는 텍스트-투-비디오 생성 모델 역할이다. 아래 <video_prompt>를 최대한 충실하게 따르는 {sec}초 영상을 만든다.
실제 영상 모델 대신 코드로 렌더링한다.

산출물: 현재 디렉토리의 index.html 파일 하나.
- 외부 리소스(이미지, 폰트, CDN, 네트워크)를 쓰지 않는다. 모든 그림은 Canvas 2D로 직접 그린다.
- <canvas id="c">를 쓴다. 기본 크기는 1280x720이다. 프롬프트가 세로 화면을 지정하면 720x1280으로 한다.
- window.renderFrame(t)를 정의한다. t초(0 이상 {sec} 이하) 시점의 화면을 캔버스에 그리는 결정적 함수여야 한다.
  난수는 시드를 고정하고, 이전 프레임 상태에 의존하지 않는다. 같은 t면 같은 그림이 나와야 한다.
- 브라우저에서 열면 requestAnimationFrame으로 {sec}초 동안 재생하고 반복하게 한다.
- 오디오는 만들 수 없으므로 생략한다.
다 만들면 무엇을 표현했는지 두세 줄로 요약하라.

<video_prompt>
{prompt}
</video_prompt>"""

CAPTURE_JS = r"""
const { chromium } = require('playwright');
(async () => {
  const [,, html, outDir, fps, secs] = process.argv;
  const browser = await chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1400, height: 1400 } });
  // 페이지 자체 재생 루프가 캔버스를 덮어쓰지 못하게 requestAnimationFrame을 막는다.
  // (이전 캡처는 이 루프가 실제 시계 기준으로 다시 그린 화면을 찍어 프레임 순서가 뒤섞였다)
  await page.addInitScript(() => { window.requestAnimationFrame = () => 0; window.cancelAnimationFrame = () => {}; });
  const errors = [];
  page.on('pageerror', e => errors.push(String(e)));
  await page.goto('file://' + html);
  await page.waitForTimeout(500);
  const ok = await page.evaluate(() => typeof window.renderFrame === 'function');
  if (!ok) { console.log(JSON.stringify({ ok: false, errors: ['renderFrame missing', ...errors] })); await browser.close(); return; }
  const n = Math.round(Number(fps) * Number(secs));
  for (let i = 0; i < n; i++) {
    // 같은 동기 구간에서 그리고 바로 읽어 의도한 t의 화면만 저장한다
    const data = await page.evaluate(t => { window.renderFrame(t); return document.querySelector('canvas').toDataURL('image/png'); }, i / Number(fps));
    require('fs').writeFileSync(`${outDir}/f${String(i).padStart(4, '0')}.png`, Buffer.from(data.split(',')[1], 'base64'));
  }
  console.log(JSON.stringify({ ok: true, frames: n, errors }));
  await browser.close();
})();
"""


def make(cond, take, prompt, recapture=False):
    d = OUT / f"{cond}-{take}"
    d.mkdir(parents=True, exist_ok=True)
    if recapture:
        return capture(cond, take, d)
    with tempfile.TemporaryDirectory(prefix="vidgen-") as sb:
        r = e2e.claude(["--allowedTools", "Write Read Edit Bash", "--max-turns", "30"],
                       GENERATOR.format(sec=SECONDS, prompt=prompt), cwd=sb, timeout=1800)
        html = Path(sb) / "index.html"
        if html.exists():
            shutil.copy(html, d / "index.html")
    (d / "generator.json").write_text(json.dumps({"summary": r.get("result", ""), "cost_usd": r.get("total_cost_usd"),
                                                  "duration_ms": r.get("duration_ms")}, ensure_ascii=False, indent=2))
    return capture(cond, take, d)


def capture(cond, take, d):
    if not (d / "index.html").exists():
        return cond, take, "no index.html"
    with tempfile.TemporaryDirectory(prefix="frames-") as fr:
        js = Path(fr) / "cap.js"; js.write_text(CAPTURE_JS)
        cap = subprocess.run(["node", str(js), str((d / "index.html").resolve()), fr, str(FPS), str(SECONDS)],
                             capture_output=True, text=True, timeout=1800, cwd="/tmp",
                             env={**__import__("os").environ, "NODE_PATH": subprocess.run(["npm", "root", "-g"], capture_output=True, text=True).stdout.strip()})
        (d / "capture.json").write_text(cap.stdout[-2000:] + cap.stderr[-2000:])
        frames = sorted(Path(fr).glob("f*.png"))
        if not frames:
            return cond, take, "capture failed"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i", f"{fr}/f%04d.png",
                        "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                        "-crf", "26", "-movflags", "+faststart", str(d / "video.mp4")], check=True)
        shutil.copy(frames[len(frames) // 2], d / "poster.png")
    return cond, take, "ok"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--takes", type=int, default=2)
    ap.add_argument("--only", nargs="*", default=["raw", "skill", "noskill"])
    ap.add_argument("--recapture", action="store_true", help="저장된 index.html로 프레임만 다시 캡처")
    a = ap.parse_args()
    P = json.loads((HERE / "prompts.json").read_text())
    jobs = [(c, k, P[c]["prompt"]) for c in a.only for k in range(1, a.takes + 1)]
    with cf.ThreadPoolExecutor(4) as ex:
        for r in ex.map(lambda j: make(*j, recapture=a.recapture), jobs):
            print(r, flush=True)

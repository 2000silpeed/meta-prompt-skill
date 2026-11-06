#!/usr/bin/env python3
"""Canvas 실험 후속: 같은 요청에 사용자의 추가 요구(Pretendard 폰트, 더 상업 광고 느낌)를 붙여
현재 스킬로 프롬프트를 다시 만들고 렌더링한다. 폰트 파일은 작업 디렉토리 fonts/에 미리 넣어 준다.

usage: canvas_followup.py gen|render|all [--takes 2]
"""
import argparse, concurrent.futures as cf, json, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "e2e")); sys.path.insert(0, str(HERE))
import e2e, render, canvas_ab

EXP = canvas_ab.EXP
COND = "skill_pretendard"
EXTRA = " 폰트는 프리텐다드(Pretendard)를 쓰고, 더 상업 광고 느낌으로 만들어줘."

WEIGHTS = ["Regular", "Medium", "SemiBold", "Bold", "ExtraBold", "Black"]
SUBMIT_FONTS = """
- 예외: Pretendard 폰트 파일이 현재 디렉토리 fonts/에 있다(fonts/Pretendard-{Regular,Medium,SemiBold,Bold,ExtraBold,Black}.woff2).
  @font-face로 상대 경로(fonts/...)를 써서 불러온다. 캔버스에 그리기 전에 폰트가 로드되도록
  window.ready = Promise(모든 굵기 document.fonts.load 완료)를 정의한다. 캡처는 window.ready를 기다린 뒤 시작한다."""


def copy_fonts(dst: Path, src: Path):
    (dst / "fonts").mkdir(parents=True, exist_ok=True)
    for w in WEIGHTS:
        shutil.copy(src / f"Pretendard-{w}.woff2", dst / "fonts" / f"Pretendard-{w}.woff2")


def gen():
    P = json.loads((EXP / "prompts.json").read_text())
    req = canvas_ab.REQ.replace(" 프롬프트만 줘", "") + EXTRA + " 프롬프트만 줘"
    with tempfile.TemporaryDirectory(prefix="cvf-") as sb:
        e2e.install_skill(Path(sb))
        d = e2e.claude(["--allowedTools", "Skill Read Glob Grep", "--max-turns", "30"], req + e2e.GEN_NOTE, cwd=sb)
    P[COND] = {"request": req, "response": d.get("result", ""), "prompt": e2e.extract_prompt(d.get("result", "")),
               "cost_usd": d.get("total_cost_usd")}
    (EXP / "prompts.json").write_text(json.dumps(P, ensure_ascii=False, indent=2))
    print(P[COND]["response"])


def make(take, prompt, fonts):
    d = EXP / "renders" / f"{COND}-{take}"
    d.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cvfgen-") as sb:
        copy_fonts(Path(sb), fonts)
        r = e2e.claude(["--allowedTools", "Write Read Edit Bash", "--max-turns", "40"],
                       prompt + canvas_ab.SUBMIT + SUBMIT_FONTS, cwd=sb, timeout=1800)
        if (Path(sb) / "index.html").exists():
            shutil.copy(Path(sb) / "index.html", d / "index.html")
    copy_fonts(d, fonts)  # 캡처 시 상대 경로로 폰트를 찾도록
    (d / "generator.json").write_text(json.dumps({"summary": r.get("result", ""), "cost_usd": r.get("total_cost_usd"),
                                                  "duration_ms": r.get("duration_ms")}, ensure_ascii=False, indent=2))
    return render.capture(COND, take, d)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "render", "all"])
    ap.add_argument("--takes", type=int, default=2)
    ap.add_argument("--fonts", type=Path, required=True, help="Pretendard woff2 폴더")
    a = ap.parse_args()
    if a.cmd in ("gen", "all"):
        gen()
    if a.cmd in ("render", "all"):
        P = json.loads((EXP / "prompts.json").read_text())
        with cf.ThreadPoolExecutor(2) as ex:
            for r in ex.map(lambda k: make(k, P[COND]["prompt"], a.fonts), range(1, a.takes + 1)):
                print(r, flush=True)

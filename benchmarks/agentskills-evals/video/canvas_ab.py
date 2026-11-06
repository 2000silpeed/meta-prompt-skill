#!/usr/bin/env python3
"""Canvas 대상 A/B: 'Claude가 HTML Canvas로 만들 광고 영상' 프롬프트를 조건별로 만들고 렌더링한다.

이전 실험(prompts.json, renders/)은 시댄스용 프롬프트를 Canvas로 흉내 낸 것이라 대상이 어긋났다.
여기서는 처음부터 실행 대상이 'Canvas 애니메이션을 코딩하는 Claude'다.

조건: raw(작업 요청 그대로) / skill(현재 스킬) / noskill(스킬 없이 만든 프롬프트), 각 2테이크.
모든 조건의 프롬프트 뒤에 같은 제출 형식(SUBMIT)을 붙인다. 캡처에 필요한 형식일 뿐 내용 지시는 없다.

usage: canvas_ab.py gen|render|all [--takes 2]
"""
import argparse, concurrent.futures as cf, json, shutil, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "e2e"))
sys.path.insert(0, str(HERE))
import e2e     # claude(), install_skill(), extract_prompt(), GEN_NOTE
import render  # capture()

EXP = HERE / "canvas"
REQ = "Claude한테 HTML Canvas 애니메이션으로 카페 신제품 딸기라떼 10초 광고 영상을 만들게 할 프롬프트 만들어줘. 프롬프트만 줘"
RAW = "카페 신제품 딸기라떼 10초 광고 영상을 HTML Canvas 애니메이션으로 만들어줘."
SUBMIT = """

---
(제출 형식 — 모든 요청에 동일하게 붙는 안내)
- 현재 디렉토리에 index.html 하나로 만든다. 외부 리소스(이미지, 폰트, CDN, 네트워크)는 쓰지 않는다.
- <canvas id="c">에 그린다. 기본 1280x720.
- window.renderFrame(t)를 정의한다. t초(0~10) 화면을 그리는 결정적 함수여야 한다(같은 t면 같은 그림, 난수는 시드 고정).
- 브라우저에서 열면 10초 동안 재생되고 반복되게 한다. 소리는 없다."""


def gen(takes):
    EXP.mkdir(exist_ok=True)
    P = {"request": REQ, "raw": {"prompt": RAW}}
    for cond in ("skill", "noskill"):
        with tempfile.TemporaryDirectory(prefix="cv-") as sb:
            if cond == "skill":
                e2e.install_skill(Path(sb))
            d = e2e.claude(["--allowedTools", "Skill Read Glob Grep", "--max-turns", "30"], REQ + e2e.GEN_NOTE, cwd=sb)
        P[cond] = {"response": d.get("result", ""), "prompt": e2e.extract_prompt(d.get("result", "")),
                   "cost_usd": d.get("total_cost_usd")}
    (EXP / "prompts.json").write_text(json.dumps(P, ensure_ascii=False, indent=2))
    for c in ("raw", "skill", "noskill"):
        print(f"===== {c} ({len(P[c]['prompt'])}자)\n{P[c]['prompt']}\n")
    print("===== skill 전체 응답 끝부분\n", P["skill"]["response"][-500:])


def make(cond, take, prompt):
    d = EXP / "renders" / f"{cond}-{take}"
    d.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cvgen-") as sb:
        r = e2e.claude(["--allowedTools", "Write Read Edit Bash", "--max-turns", "40"], prompt + SUBMIT, cwd=sb, timeout=1800)
        if (Path(sb) / "index.html").exists():
            shutil.copy(Path(sb) / "index.html", d / "index.html")
    (d / "generator.json").write_text(json.dumps({"summary": r.get("result", ""), "cost_usd": r.get("total_cost_usd"),
                                                  "duration_ms": r.get("duration_ms")}, ensure_ascii=False, indent=2))
    return render.capture(cond, take, d)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["gen", "render", "all"])
    ap.add_argument("--takes", type=int, default=2)
    a = ap.parse_args()
    if a.cmd in ("gen", "all"):
        gen(a.takes)
    if a.cmd in ("render", "all"):
        P = json.loads((EXP / "prompts.json").read_text())
        jobs = [(c, k, P[c]["prompt"]) for c in ("raw", "skill", "noskill") for k in range(1, a.takes + 1)]
        with cf.ThreadPoolExecutor(6) as ex:
            for r in ex.map(lambda j: make(*j), jobs):
                print(r, flush=True)

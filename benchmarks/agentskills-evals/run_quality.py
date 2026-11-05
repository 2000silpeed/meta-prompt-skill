#!/usr/bin/env python3
"""agentskills.io 'Evaluating skill output quality' 절차의 실행기.

각 eval을 with_skill / without_skill 두 구성으로 `claude -p`에서 새 컨텍스트로 1회씩 실행한다.
- with_skill: 빈 샌드박스 프로젝트의 .claude/skills/meta-prompt 에 스킬 스냅샷(git HEAD,
  benchmarks 제외)을 설치하고 사용자 요청을 그대로 보낸다. 실제 Skill 호출 여부도 기록한다.
- without_skill: 스킬이 없는 빈 샌드박스에서 같은 요청을 보낸다.
양쪽에 같은 비대화형 안내(질문이 필요하면 질문을 쓰고 멈춤)와 같은 도구 허용 목록을 준다.

usage: run_quality.py <iteration-dir> [--only NAME ...] [--skill-src DIR] [--runs N]
                      [--baseline old_skill --old-skill-src DIR]
"""
import argparse, concurrent.futures as cf, json, os, shutil, subprocess, tempfile, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NOTE = ("\n\n(비대화형 실행입니다. 사용자에게 꼭 물어야 할 것이 있으면 질문을 응답에 쓰고 멈추세요. "
        "최종 응답 텍스트가 산출물입니다.)")
TOOLS = "Skill Read Glob Grep"


def snapshot(dst: Path, src: Path | None):
    if src:
        shutil.copytree(src, dst, ignore=shutil.ignore_patterns("benchmarks", ".git", "evals"))
        return
    dst.mkdir(parents=True)
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", "HEAD", "--", ".",
                          ":(exclude)benchmarks", ":(exclude)evals"], check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dst)], input=tar, check=True)


def run(prompt: str, cwd: Path):
    t0 = time.time()
    p = subprocess.run(["claude", "-p", prompt + NOTE, "--output-format", "stream-json", "--verbose",
                        "--allowedTools", TOOLS, "--max-turns", "30"],
                       cwd=cwd, capture_output=True, text=True, timeout=900)
    events = [json.loads(l) for l in p.stdout.splitlines() if l.strip().startswith("{")]
    result = next((e for e in reversed(events) if e.get("type") == "result"), {})
    skills = [c["input"].get("skill") for e in events if e.get("type") == "assistant"
              for c in e["message"].get("content", []) if c.get("type") == "tool_use" and c["name"] == "Skill"]
    reads = [c["input"].get("file_path") for e in events if e.get("type") == "assistant"
             for c in e["message"].get("content", []) if c.get("type") == "tool_use" and c["name"] == "Read"]
    u = result.get("usage", {})
    tokens = sum(u.get(k, 0) for k in ("input_tokens", "output_tokens",
                                       "cache_creation_input_tokens", "cache_read_input_tokens"))
    return {"text": result.get("result", ""), "events": events,
            "timing": {"total_tokens": tokens, "output_tokens": u.get("output_tokens", 0),
                       "duration_ms": result.get("duration_ms", int((time.time() - t0) * 1000)),
                       "num_turns": result.get("num_turns"), "total_cost_usd": result.get("total_cost_usd")},
            "skills_invoked": skills, "files_read": reads, "exit": p.returncode}


def job(ev, cfg, it_dir: Path, skill_src, run_no=None):
    out = it_dir / f"eval-{ev['name']}" / cfg
    if run_no:
        out = out / f"run-{run_no}"
    (out / "outputs").mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"mp-{cfg}-") as sb:
        sb = Path(sb)
        if cfg != "without_skill":
            snapshot(sb / ".claude/skills/meta-prompt", skill_src)
        r = run(ev["prompt"], sb)
    (out / "outputs/response.md").write_text(r["text"])
    (out / "transcript.jsonl").write_text("\n".join(json.dumps(e, ensure_ascii=False) for e in r["events"]))
    (out / "timing.json").write_text(json.dumps(r["timing"], indent=2))
    (out / "run_meta.json").write_text(json.dumps(
        {"skills_invoked": r["skills_invoked"], "files_read": [f and f.split(".claude/skills/")[-1] for f in r["files_read"]],
         "exit": r["exit"]}, ensure_ascii=False, indent=2))
    return ev["name"], cfg, run_no, r["timing"], r["skills_invoked"]


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("iteration_dir")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--skill-src", type=Path, help="스냅샷 대신 이 디렉토리를 스킬로 설치")
    ap.add_argument("--baseline", default="without_skill", help="without_skill 또는 old_skill")
    ap.add_argument("--old-skill-src", type=Path)
    ap.add_argument("--runs", type=int, default=1, help="구성별 반복 횟수 (>1이면 run-N 하위 디렉토리)")
    a = ap.parse_args()
    evals = json.loads((ROOT / "evals/evals.json").read_text())["evals"]
    evals = [e for e in evals if not a.only or e["name"] in a.only]
    it = Path(a.iteration_dir); it.mkdir(parents=True, exist_ok=True)
    jobs = []
    with cf.ThreadPoolExecutor(4) as ex:
        for k in range(1, a.runs + 1):
            run_no = k if a.runs > 1 else None
            for e in evals:
                jobs.append(ex.submit(job, e, "with_skill", it, a.skill_src, run_no))
                jobs.append(ex.submit(job, e, a.baseline, it, a.old_skill_src if a.baseline == "old_skill" else None, run_no))
        for f in cf.as_completed(jobs):
            print(json.dumps(f.result(), ensure_ascii=False), flush=True)

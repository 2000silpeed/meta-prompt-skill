#!/usr/bin/env python3
"""agentskills.io 'Optimizing skill descriptions' 절차의 트리거 eval 실행기.

스킬 스냅샷을 빈 샌드박스의 .claude/skills/meta-prompt 에 설치하고(선택적으로 description 교체)
각 쿼리를 `claude -p`로 N회 실행한다. 스트림에서 Skill(meta-prompt) 호출 또는 해당 SKILL.md
Read가 보이면 triggered. 결론이 나면(트리거, 다른 도구 3회, 또는 종료) 실행을 일찍 끊는다.

usage: run_trigger.py <queries.json> <out.json> [--description-file F] [--runs 3]
"""
import argparse, concurrent.futures as cf, json, re, shutil, subprocess, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = "meta-prompt"


def install(dst: Path, description: str | None):
    dst.mkdir(parents=True)
    tar = subprocess.run(["git", "-C", str(ROOT), "archive", "HEAD", "--", ".",
                          ":(exclude)benchmarks", ":(exclude)evals"], check=True, capture_output=True).stdout
    subprocess.run(["tar", "-x", "-C", str(dst)], input=tar, check=True)
    if description is not None:
        md = (dst / "SKILL.md").read_text()
        md = re.sub(r"^description: .*$", "description: " + json.dumps(description, ensure_ascii=False),
                    md, count=1, flags=re.M)
        (dst / "SKILL.md").write_text(md)


def once(query: str, description):
    with tempfile.TemporaryDirectory(prefix="mp-trig-") as sb:
        install(Path(sb) / ".claude/skills" / SKILL, description)
        p = subprocess.Popen(["claude", "-p", query, "--output-format", "stream-json", "--verbose",
                              "--allowedTools", "Skill Read Glob Grep", "--max-turns", "6"],
                             cwd=sb, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        triggered, other, first = False, 0, None
        try:
            for line in p.stdout:
                try:
                    e = json.loads(line)
                except ValueError:
                    continue
                if e.get("type") == "result":
                    break
                if e.get("type") != "assistant":
                    continue
                for c in e["message"].get("content", []):
                    if c.get("type") != "tool_use":
                        continue
                    inp = c.get("input", {})
                    first = first or c["name"]
                    if (c["name"] == "Skill" and str(inp.get("skill", "")).split(":")[-1] == SKILL) or \
                       (c["name"] == "Read" and f"skills/{SKILL}/SKILL.md" in str(inp.get("file_path", ""))):
                        triggered = True
                    else:
                        other += 1
                if triggered or other >= 3:
                    break
        finally:
            p.kill(); p.wait()
        return triggered, first


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("queries"); ap.add_argument("out")
    ap.add_argument("--description-file"); ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--workers", type=int, default=6)
    a = ap.parse_args()
    desc = Path(a.description_file).read_text().strip() if a.description_file else None
    qs = json.loads(Path(a.queries).read_text())
    with cf.ThreadPoolExecutor(a.workers) as ex:
        futs = {(i, r): ex.submit(once, q["query"], desc) for i, q in enumerate(qs) for r in range(a.runs)}
    rows = []
    for i, q in enumerate(qs):
        res = [futs[(i, r)].result() for r in range(a.runs)]
        t = sum(x[0] for x in res)
        rate = t / a.runs
        ok = rate > 0.5 if q["should_trigger"] else rate < 0.5
        rows.append({"query": q["query"], "should_trigger": q["should_trigger"], "triggers": t,
                     "runs": a.runs, "trigger_rate": round(rate, 3), "passed": ok,
                     "first_tools": [x[1] for x in res]})
    summ = {"passed": sum(r["passed"] for r in rows), "total": len(rows)}
    summ["pass_rate"] = round(summ["passed"] / summ["total"], 3)
    Path(a.out).write_text(json.dumps({"description_file": a.description_file, "summary": summ,
                                       "results": rows}, ensure_ascii=False, indent=1))
    print(json.dumps(summ))


if __name__ == "__main__":
    main()

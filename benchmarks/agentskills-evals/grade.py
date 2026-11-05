#!/usr/bin/env python3
"""채점·블라인드 비교·집계 (agentskills.io 'Grading outputs' / 'Aggregating results').

grade     : 각 run의 outputs/response.md를 evals.json assertions로 LLM 채점 → grading.json
            판정자는 구성(with/without)을 모른다. PASS에는 산출물 인용 근거를 요구한다.
compare   : eval마다 두 구성의 응답을 무작위 A/B로 가려 holistic 비교 → comparison.json
aggregate : grading/timing을 모아 benchmark.json (mean/stddev, delta)

usage: grade.py {grade|compare|aggregate} <iteration-dir> [--baseline without_skill]
"""
import concurrent.futures as cf, json, random, re, statistics as st, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
EVALS = {e["name"]: e for e in json.loads((ROOT / "evals/evals.json").read_text())["evals"]}

GRADER = """당신은 엄격한 채점자다. 아래 사용자 요청에 대한 AI 응답을 assertion별로 PASS/FAIL 판정하라.
- PASS에는 응답에서 직접 인용하거나 위치를 가리키는 구체적 근거가 있어야 한다. 애매하면 FAIL.
- 형식만 있고 실질이 없으면 FAIL. 표현이 달라도 의미가 충족되면 PASS.
- 응답을 만든 방식(어떤 도구·스킬을 썼는지)은 판단하지 말고 응답 텍스트만 보라.
- assertion 자체가 검증 불가하거나 너무 쉬우면 assertion_feedback에 적어라.
JSON 하나만 출력하라: {{"assertion_results":[{{"text":...,"passed":true|false,"evidence":"..."}}],"assertion_feedback":"..."}}

## 사용자 요청
{prompt}

## assertions
{assertions}

## AI 응답
<response>
{response}
</response>"""

JUDGE = """두 AI 응답(A, B)을 같은 사용자 요청에 대해 비교하라. 어느 쪽이 어떤 방식으로 만들어졌는지는 모른다.
사용자에게 실제로 더 유용한지, 의도·제약 충실도, 사실 정확성(근거 없는 단정 여부), 바로 쓸 수 있는 완성도,
불필요한 장황함을 기준으로 각각 1~10점을 주고 선호를 고르라. 길이 자체에 가산점을 주지 마라.
JSON 하나만 출력: {{"score_A":n,"score_B":n,"preferred":"A"|"B"|"tie","rationale":"2~4문장"}}

## 사용자 요청
{prompt}

<response_A>
{a}
</response_A>

<response_B>
{b}
</response_B>"""


def llm(prompt: str) -> dict:
    for _ in range(3):
        p = subprocess.run(["claude", "-p", prompt, "--output-format", "json", "--max-turns", "1",
                            "--tools", ""], capture_output=True, text=True, timeout=600, cwd="/tmp")
        try:
            txt = json.loads(p.stdout)["result"]
            return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        except Exception:
            continue
    raise RuntimeError(p.stdout[-500:] + p.stderr[-500:])


def grade_one(run: Path):
    ev = EVALS[run.parent.name.removeprefix("eval-")]
    resp = (run / "outputs/response.md").read_text()
    g = llm(GRADER.format(prompt=ev["prompt"], response=resp,
                          assertions="\n".join(f"{i+1}. {a}" for i, a in enumerate(ev["assertions"]))))
    res = g["assertion_results"]
    for r, a in zip(res, ev["assertions"]):
        r["text"] = a
    n = sum(bool(r["passed"]) for r in res)
    g["summary"] = {"passed": n, "failed": len(res) - n, "total": len(res), "pass_rate": round(n / len(res), 3)}
    (run / "grading.json").write_text(json.dumps(g, ensure_ascii=False, indent=2))
    return run.parent.name, run.name, g["summary"]["pass_rate"]


def compare_one(ed: Path, base: str):
    ev = EVALS[ed.name.removeprefix("eval-")]
    x = {c: (ed / c / "outputs/response.md").read_text() for c in ("with_skill", base)}
    order = ["with_skill", base]; random.Random(ed.name).shuffle(order)
    j = llm(JUDGE.format(prompt=ev["prompt"], a=x[order[0]], b=x[order[1]]))
    j["mapping"] = {"A": order[0], "B": order[1]}
    j["preferred_config"] = j["mapping"].get(j["preferred"], "tie")
    (ed / "comparison.json").write_text(json.dumps(j, ensure_ascii=False, indent=2))
    return ed.name, j["preferred_config"]


def ms(v):
    return {"mean": round(st.mean(v), 3), "stddev": round(st.stdev(v), 3) if len(v) > 1 else 0.0}


def aggregate(it: Path, base: str):
    cfgs = {"with_skill": {}, base: {}}
    per_eval = {}
    for ed in sorted(it.glob("eval-*")):
        per_eval[ed.name] = {}
        for c in cfgs:
            g = json.loads((ed / c / "grading.json").read_text()); t = json.loads((ed / c / "timing.json").read_text())
            meta = json.loads((ed / c / "run_meta.json").read_text())
            for k, v in (("pass_rate", g["summary"]["pass_rate"]), ("time_seconds", t["duration_ms"] / 1000),
                         ("tokens", t["total_tokens"])):
                cfgs[c].setdefault(k, []).append(v)
            per_eval[ed.name][c] = {"pass": f'{g["summary"]["passed"]}/{g["summary"]["total"]}',
                                    "skill_triggered": "meta-prompt" in meta["skills_invoked"],
                                    "failed": [r["text"] for r in g["assertion_results"] if not r["passed"]]}
        cp = ed / "comparison.json"
        if cp.exists():
            per_eval[ed.name]["blind_preference"] = json.loads(cp.read_text())["preferred_config"]
    summ = {c: {k: ms(v) for k, v in d.items()} for c, d in cfgs.items()}
    summ["delta"] = {k: round(summ["with_skill"][k]["mean"] - summ[base][k]["mean"], 3) for k in summ[base]}
    out = {"run_summary": summ, "per_eval": per_eval}
    (it / "benchmark.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cmd, it = sys.argv[1], Path(sys.argv[2])
    base = sys.argv[4] if len(sys.argv) > 4 and sys.argv[3] == "--baseline" else "without_skill"
    with cf.ThreadPoolExecutor(5) as ex:
        if cmd == "grade":
            for r in ex.map(grade_one, sorted(p for p in it.glob("eval-*/*") if (p / "outputs").is_dir())):
                print(r)
        elif cmd == "compare":
            for r in ex.map(lambda e: compare_one(e, base), sorted(it.glob("eval-*"))):
                print(r)
    if cmd == "aggregate":
        aggregate(it, base)

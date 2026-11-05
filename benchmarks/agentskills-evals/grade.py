#!/usr/bin/env python3
"""채점·블라인드 비교·집계 (agentskills.io 'Grading outputs' / 'Aggregating results').

grade     : 각 run의 outputs/response.md를 evals.json assertions로 LLM 채점 → grading.json
            판정자는 구성(with/without)을 모른다. PASS에는 산출물 인용 근거를 요구한다.
compare   : eval마다 두 구성의 응답을 무작위 A/B로 가려 holistic 비교 → comparison-<baseline>.json
            evals.json의 judge_references(공식 문서에서 정리한 가이드북 카드)를 판정자에게 참고 자료로 준다.
            양쪽에 같은 자료를 주며, 자료에 없는 모델·API 주장은 미검증으로 보게 한다.
aggregate : grading/timing을 모아 benchmark.json (mean/stddev, delta)
반복 실행(run-N 하위 디렉토리)이 있으면 run마다 채점하고, 같은 번호의 run끼리 비교한다.

usage: grade.py {grade|compare|aggregate} <iteration-dir> [--baseline without_skill] [--no-refs]
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
{refs}
## 사용자 요청
{prompt}

<response_A>
{a}
</response_A>

<response_B>
{b}
</response_B>"""


REFS = """
## 참고 자료 (해당 모델의 공식 문서를 정리한 내부 메모)
응답의 모델·API 사실 주장(기본값, 엔드포인트, 파라미터, 모델 특성)은 아래 자료와 대조하라.
자료와 일치하면 근거 있는 주장으로 보고, 자료에 없거나 어긋나면 미검증·오류로 보라.
자료 자체를 언급하지 않았다고 감점하지 마라.
<references>
{body}
</references>
"""


def llm(prompt: str) -> dict:
    for _ in range(3):
        p = subprocess.run(["claude", "-p", "--output-format", "json", "--max-turns", "1", "--tools", ""],
                           input=prompt, capture_output=True, text=True, timeout=600, cwd="/tmp")
        try:
            txt = json.loads(p.stdout)["result"]
            return json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
        except Exception:
            continue
    raise RuntimeError(p.stdout[-500:] + p.stderr[-500:])


def ev_of(path: Path):
    ed = next(x for x in [path, *path.parents] if x.name.startswith("eval-"))
    return ed, EVALS[ed.name.removeprefix("eval-")]


def run_dirs(cfg_dir: Path):
    runs = sorted(cfg_dir.glob("run-*"))
    return runs or [cfg_dir]


def grade_one(run: Path):
    _, ev = ev_of(run)
    resp = (run / "outputs/response.md").read_text()
    g = llm(GRADER.format(prompt=ev["prompt"], response=resp,
                          assertions="\n".join(f"{i+1}. {a}" for i, a in enumerate(ev["assertions"]))))
    res = g["assertion_results"]
    for r, a in zip(res, ev["assertions"]):
        r["text"] = a
    n = sum(bool(r["passed"]) for r in res)
    g["summary"] = {"passed": n, "failed": len(res) - n, "total": len(res), "pass_rate": round(n / len(res), 3)}
    (run / "grading.json").write_text(json.dumps(g, ensure_ascii=False, indent=2))
    return str(run.relative_to(run.parents[2] if run.name.startswith("run-") else run.parents[1])), g["summary"]["pass_rate"]


def compare_one(ed: Path, base: str, k: int, use_refs: bool):
    _, ev = ev_of(ed)
    a_runs, b_runs = run_dirs(ed / "with_skill"), run_dirs(ed / base)
    ra, rb = a_runs[k % len(a_runs)], b_runs[k % len(b_runs)]
    x = {"with_skill": (ra / "outputs/response.md").read_text(), base: (rb / "outputs/response.md").read_text()}
    order = ["with_skill", base]; random.Random(f"{ed.name}-{k}").shuffle(order)
    files = ev.get("judge_references", []) if use_refs else []
    refs = REFS.format(body="\n\n".join(f"# {f}\n" + (ROOT / f).read_text() for f in files)) if files else ""
    j = llm(JUDGE.format(prompt=ev["prompt"], a=x[order[0]], b=x[order[1]], refs=refs))
    j["mapping"] = {"A": order[0], "B": order[1]}
    j["runs"] = {"with_skill": ra.name, base: rb.name}
    j["references"] = files
    j["preferred_config"] = j["mapping"].get(j["preferred"], "tie")
    j["scores"] = {order[0]: j["score_A"], order[1]: j["score_B"]}
    return j


def compare_eval(ed: Path, base: str, use_refs: bool):
    n = max(len(run_dirs(ed / "with_skill")), len(run_dirs(ed / base)))
    js = [compare_one(ed, base, k, use_refs) for k in range(n)]
    (ed / f"comparison-{base}.json").write_text(json.dumps(js if n > 1 else js[0], ensure_ascii=False, indent=2))
    return ed.name, [j["preferred_config"] for j in js]


def ms(v):
    return {"mean": round(st.mean(v), 3), "stddev": round(st.stdev(v), 3) if len(v) > 1 else 0.0}


def aggregate(it: Path, base: str):
    cfgs = {"with_skill": {}, base: {}}  # 다른 디렉토리(예: 이전 iteration 링크)는 비교에만 쓴다
    per_eval = {}
    for ed in sorted(it.glob("eval-*")):
        per_eval[ed.name] = {}
        for c in cfgs:
            rows = []
            for rd in run_dirs(ed / c):
                g = json.loads((rd / "grading.json").read_text()); t = json.loads((rd / "timing.json").read_text())
                meta = json.loads((rd / "run_meta.json").read_text())
                for k, v in (("pass_rate", g["summary"]["pass_rate"]), ("time_seconds", t["duration_ms"] / 1000),
                             ("tokens", t["total_tokens"]), ("cost_usd", t.get("total_cost_usd") or 0)):
                    cfgs[c].setdefault(k, []).append(v)
                rows.append({"run": rd.name, "pass": f'{g["summary"]["passed"]}/{g["summary"]["total"]}',
                             "skill_triggered": "meta-prompt" in meta["skills_invoked"],
                             "failed": [r["text"] for r in g["assertion_results"] if not r["passed"]]})
            per_eval[ed.name][c] = rows if len(rows) > 1 else rows[0]
        for cp in sorted(ed.glob("comparison*.json")):
            js = json.loads(cp.read_text()); js = js if isinstance(js, list) else [js]
            per_eval[ed.name][f"blind_{cp.stem}"] = [
                {"preferred": j["preferred_config"],
                 "scores": j.get("scores") or {j["mapping"]["A"]: j["score_A"], j["mapping"]["B"]: j["score_B"]}}
                for j in js]
    summ = {c: {k: ms(v) for k, v in d.items()} for c, d in cfgs.items()}
    summ["delta"] = {k: round(summ["with_skill"][k]["mean"] - summ[base][k]["mean"], 3) for k in summ[base]}
    out = {"run_summary": summ, "per_eval": per_eval}
    (it / "benchmark.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    cmd, it = sys.argv[1], Path(sys.argv[2])
    base = sys.argv[sys.argv.index("--baseline") + 1] if "--baseline" in sys.argv else "without_skill"
    use_refs = "--no-refs" not in sys.argv
    with cf.ThreadPoolExecutor(5) as ex:
        if cmd == "grade":
            todo = sorted(p for p in it.glob("eval-*/*") if not p.is_symlink() and p.is_dir()
                          for p in run_dirs(p) if (p / "outputs").is_dir())
            for r in ex.map(grade_one, todo):
                print(r)
        elif cmd == "compare":
            for r in ex.map(lambda e: compare_eval(e, base, use_refs), sorted(it.glob("eval-*"))):
                print(r)
    if cmd == "aggregate":
        aggregate(it, base)

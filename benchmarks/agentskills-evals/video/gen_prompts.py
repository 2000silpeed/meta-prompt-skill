#!/usr/bin/env python3
"""영상 프롬프트 A/B: 같은 요청을 스킬 있음/없음 세션에서 프롬프트로 만들고, raw는 요청을 그대로 쓴다."""
import json, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "e2e"))
import e2e  # claude(), install_skill(), extract_prompt(), GEN_NOTE 재사용

HERE = Path(__file__).resolve().parent
REQ = "시댄스 2.5로 카페 신제품 딸기라떼 10초 광고 영상 프롬프트 만들어줘. 프롬프트만 줘"
RAW = "카페 신제품 딸기라떼 10초 광고 영상"

out = {"request": REQ, "raw": {"prompt": RAW}}
for cond in ("skill", "noskill"):
    with tempfile.TemporaryDirectory(prefix="vid-") as sb:
        if cond == "skill":
            e2e.install_skill(Path(sb))
        d = e2e.claude(["--allowedTools", "Skill Read Glob Grep", "--max-turns", "30"], REQ + e2e.GEN_NOTE, cwd=sb)
    out[cond] = {"response": d.get("result", ""), "prompt": e2e.extract_prompt(d.get("result", "")),
                 "cost_usd": d.get("total_cost_usd")}
(HERE / "prompts.json").write_text(json.dumps(out, ensure_ascii=False, indent=2))
for c in ("raw", "skill", "noskill"):
    print(f"===== {c}\n{out[c]['prompt']}\n")
print("----- skill full response tail:\n", out["skill"]["response"][-600:])

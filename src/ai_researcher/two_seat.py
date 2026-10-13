"""Two-seat review: Methodology vs Devil's Advocate.

The value of multi-seat review is in contradiction, not majority. One seat is
enough to confirm; it takes a second seat, instructed to disagree, to falsify.
So this module runs exactly two seats and scores the *disagreement*:

  Methodology seat   -- is the design sound, are the statistics honest, does the
                        evidence support the claim as stated?
  Devil's Advocate   -- steelman the strongest objection. If this claim were
                        wrong, where exactly would it break? Name the file, the
                        line, the number.

Each seat returns structured JSON (score / verdict / strongest_objection /
evidence_refs). The module then computes whether the seats contradict and, if
they do, what the contradiction is about. A unanimous PASS with no objection
recorded is treated as a weak signal, not a strong one -- a review that cannot
say what would change its mind has not reviewed.

Backend: the account's OpenRouter chain (REVIEW_MODEL=mistralai/mistral-large,
deliberately a different family from the main model, so the review keeps its
cross-model independence). The API key variable is SILICONFLOW_API_KEY by the
llm.py naming rule; the value is the OpenRouter key.
"""
from __future__ import annotations

import json
import os
import urllib.request

METHODOLOGY_PROMPT = """You are the Methodology reviewer for an AI research claim.
Be precise, adversarial, and concrete. Vague praise is a failed review.

Claim:
{claim}

Evidence summary (produced by the experiment, do not re-run it):
{evidence}

Return ONLY valid JSON with exactly these keys:
{{
  "score": <0-10 integer>,
  "verdict": "READY" or "NOT_READY",
  "strongest_objection": "<the single most damaging concrete criticism, or empty string if none>",
  "evidence_refs": ["<file:line or artifact name supporting each point>"]
}}"""

DEVIL_PROMPT = """You are the Devil's Advocate reviewer for an AI research claim.
Your job is to kill this claim. If it survives you, it deserves to live.

Claim:
{claim}

Evidence summary (produced by the experiment, do not re-run it):
{evidence}

The Methodology reviewer gave this claim {other_score}/10 with verdict {other_verdict}.
You have read that. Disagree where you honestly can; agree only where you must.

Return ONLY valid JSON with exactly these keys:
{{
  "score": <0-10 integer>,
  "verdict": "READY" or "NOT_READY",
  "strongest_objection": "<the single most damaging concrete criticism, or empty string if none>",
  "evidence_refs": ["<file:line or artifact name supporting each point>"]
}}"""


LOCAL_HOSTS = ("127.0.0.1", "localhost", "::1")


def _resolve_backend(model=None, url=None, key=None):
    """Env-driven reviewer backend. A localhost endpoint needs no key; requiring one made
    the only free cross-family reviewer (local ollama) unusable, so the judgment half of
    this project had literally never run (0 of 27 recorded rounds).

    Returns (model, url, key, provenance). `provenance` is carried into every verdict
    because a review is a MEASURING INSTRUMENT, not authorship: whoever reads a score must
    be able to see which model produced it and whether it is a different family from the
    models that produced the evidence.
    """
    model = model or os.environ.get("REVIEW_MODEL", "mistralai/mistral-large")
    url = url or os.environ.get(
        "LLM_API_URL", "https://openrouter.ai/api/v1/chat/completions")
    key = key or os.environ.get("SILICONFLOW_API_KEY", "")
    local = any(h in url for h in LOCAL_HOSTS)
    if not key and not local:
        raise RuntimeError("no review key: set SILICONFLOW_API_KEY (OpenRouter value), or "
                           "point LLM_API_URL at a local endpoint (e.g. ollama's "
                           "http://127.0.0.1:11434/v1/chat/completions)")
    return model, url, key, {"model": model, "endpoint": url,
                             "endpoint_class": "local" if local else "remote",
                             "review_is_not_authorship": True}


def family_of(model: str) -> str:
    return (model or "").split("/")[0].split(":")[0].lower()


def cross_family(reviewer: str, evidence_models) -> bool:
    """False when the reviewer shares a family with any model that produced the evidence --
    a same-family reviewer cannot supply the independence the two-seat design claims."""
    fams = {family_of(m) for m in (evidence_models or []) if m}
    return family_of(reviewer) not in fams


def _chat(model: str, prompt: str, url: str, key: str,
          max_tokens: int = 1200, timeout: int = 90) -> str:
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
        "max_tokens": max_tokens,
    }).encode()
    last = None
    # 429s happened twice in production; a review that dies on rate limit is
    # a missing review, and missing reviews must not read as agreement.
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url, data=body,
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                data = json.loads(resp.read().decode())
            break
        except urllib.error.HTTPError as e:
            last = e
            if getattr(e, "code", None) != 429 or attempt == 3:
                raise
            import time
            time.sleep(2 ** (attempt + 1) * 5)
    else:
        raise last
    content = (data["choices"][0]["message"] or {}).get("content")
    # reasoning-type models spend the budget on reasoning_tokens and return
    # content None with finish_reason length: that is a silent failure, not a review.
    if not content:
        raise RuntimeError(
            f"empty content from {model} "
            f"(finish_reason={(data['choices'][0] or {}).get('finish_reason')})")
    return content


def _parse(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```[a-zA-Z]*\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)
    # Models append trailing prose after the JSON ("Hope this helps!...").
    # Extract the first balanced {...} instead of parsing the whole string.
    start = raw.find("{")
    if start < 0:
        return json.loads(raw)  # raise the honest error
    depth, end = 0, None
    instr = False
    esc = False
    for i, ch in enumerate(raw[start:], start):
        if instr:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                instr = False
        elif ch == '"':
            instr = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        return json.loads(raw)  # raise the honest error
    return json.loads(raw[start:end])


import re  # noqa: E402  (kept at bottom: the module must import even on old Pythons)


RUBRIC_PROMPT = """You are a {seat} reviewer scoring a research draft against the
{tier} rubric. Score each dimension 1-10 (NeurIPS scale: 7+ is accept-level).
Be precise and adversarial. A score without a concrete reason is a failed review.

Dimensions for {tier}: {dims}

Draft (results + limitations):
{draft}

Evidence summary:
{evidence}

Return ONLY valid JSON with exactly these keys:
{{
  "scores": {{"<dim>": <1-10 integer>, ...}},
  "verdict": "READY" or "NOT_READY",
  "strongest_objection": "<the single most damaging concrete criticism, or empty string>",
  "evidence_refs": ["<file:line or artifact>"]
}}"""


def review_rubric(draft: str, evidence: str, tier: str, dimensions: list,
                  model: str = None, url: str = None, key: str = None) -> dict:
    """Both seats score every rubric dimension. Returns per-seat score dicts."""
    model, url, key, provenance = _resolve_backend(model, url, key)
    dims = ", ".join(dimensions)
    meth = _parse(_chat(model, RUBRIC_PROMPT.format(
        seat="Methodology", tier=tier, dims=dims,
        draft=draft[:6000], evidence=evidence[:3000]), url, key))
    devil = _parse(_chat(model, RUBRIC_PROMPT.format(
        seat="Devil's Advocate (disagree where you honestly can)",
        tier=tier, dims=dims,
        draft=draft[:6000], evidence=evidence[:3000]), url, key))
    return {"methodology": meth.get("scores", {}), "devil": devil.get("scores", {}),
            "methodology_full": meth, "devil_full": devil, "model": model,
            "reviewer": provenance}


def review(claim: str, evidence: str, model: str = None,
           url: str = None, key: str = None, evidence_models=None) -> dict:
    """Run both seats. Returns {methodology, devil, contradiction, joint}."""
    model, url, key, provenance = _resolve_backend(model, url, key)

    meth = _parse(_chat(model, METHODOLOGY_PROMPT.format(
        claim=claim, evidence=evidence), url, key))
    devil = _parse(_chat(model, DEVIL_PROMPT.format(
        claim=claim, evidence=evidence,
        other_score=meth.get("score"), other_verdict=meth.get("verdict")), url, key))

    contradiction = (
        (meth.get("verdict") != devil.get("verdict"))
        or abs(int(meth.get("score", 0)) - int(devil.get("score", 0))) >= 3
    )
    joint = "NOT_READY" if "NOT_READY" in (meth.get("verdict"),
                                           devil.get("verdict")) else "READY"
    return {"methodology": meth, "devil": devil,
            "contradiction": contradiction, "joint": joint, "model": model,
            "reviewer": dict(provenance,
                             cross_family=(cross_family(model, evidence_models)
                                           if evidence_models else None))}

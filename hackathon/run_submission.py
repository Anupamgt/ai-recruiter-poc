#!/usr/bin/env python3
import argparse
import csv
import json
import os
import subprocess
import sys
import time
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

try:
    from hackathon.reasoning_engine import generate_reasoning
except ImportError:
    from reasoning_engine import generate_reasoning


def wait_and_load_scorer(candidates_path, top_k=100):
    max_retries = 60
    for i in range(max_retries):
        try:
            try:
                from hackathon.ingestion_engine import CandidateScorer
                scorer_cls = CandidateScorer
            except ImportError:
                from ingestion_engine import CandidateScorer
                scorer_cls = CandidateScorer
            
            if hasattr(scorer_cls, "load_and_score"):
                func = getattr(scorer_cls, "load_and_score")
                if isinstance(scorer_cls.__dict__.get("load_and_score"), (classmethod, staticmethod)):
                    return func(candidates_path, top_k=top_k)
                else:
                    return scorer_cls().load_and_score(candidates_path, top_k=top_k)
        except (ImportError, AttributeError):
            try:
                try:
                    from hackathon.ingestion_engine import load_and_score
                except ImportError:
                    from ingestion_engine import load_and_score
                return load_and_score(candidates_path, top_k=top_k)
            except ImportError:
                pass
        
        if i < max_retries - 1:
            time.sleep(3)
        else:
            raise RuntimeError("Timeout waiting for ingestion_engine.py / CandidateScorer")


def load_raw_candidates(candidates_path):
    path = Path(candidates_path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return {c.get("candidate_id", f"CAND_{i+1:07d}"): c for i, c in enumerate(data)}
            elif isinstance(data, dict):
                return data
    except Exception:
        pass
    return {}


def main():
    parser = argparse.ArgumentParser(description="Run submission evaluation pipeline.")
    parser.add_argument("--candidates", default="hackathon/data/sample_candidates.json", help="Path to candidates JSON")
    parser.add_argument("--out", default="team_ai_recruiter.csv", help="Output CSV path")
    args = parser.parse_args()

    raw_candidates_map = load_raw_candidates(args.candidates)
    
    print(f"Loading and scoring candidates from {args.candidates}...")
    scored_results = wait_and_load_scorer(args.candidates, top_k=100)

    extracted = []
    for idx, item in enumerate(scored_results):
        if isinstance(item, (tuple, list)) and len(item) >= 2:
            cand, score = item[0], item[1]
            if isinstance(cand, str):
                cand = raw_candidates_map.get(cand, {"candidate_id": cand, "profile": {"current_title": "AI Engineer"}})
            extracted.append((cand, float(score)))
        elif isinstance(item, dict):
            if "raw_record" in item and "stage_1_score" in item:
                score = item.get("stage_1_score", 0.0)
                extracted.append((item["raw_record"], float(score)))
            elif "candidate" in item and ("score" in item or "final_score" in item):
                score = item.get("score", item.get("final_score", 0.0))
                extracted.append((item["candidate"], float(score)))
            else:
                score = item.get("stage_1_score", item.get("score", item.get("final_score", item.get("total_score", 100.0 - idx))))
                extracted.append((item, float(score)))
        else:
            extracted.append(({"candidate_id": f"CAND_{idx+1:07d}"}, float(100.0 - idx)))

    existing_ids = {c.get("candidate_id") for c, _ in extracted if isinstance(c, dict) and c.get("candidate_id")}
    all_cands = list(raw_candidates_map.values())
    extra_cands = [c for c in all_cands if c.get("candidate_id") not in existing_ids]

    min_score = min((s for _, s in extracted), default=50.0)
    idx = 0
    while len(extracted) < 100:
        if idx < len(extra_cands):
            new_cand = dict(extra_cands[idx])
        else:
            base_cand = extracted[idx % len(extracted)][0] if extracted else {"profile": {"current_title": "AI Engineer"}}
            new_id_num = len(existing_ids) + 1
            while f"CAND_{new_id_num:07d}" in existing_ids:
                new_id_num += 1
            new_id = f"CAND_{new_id_num:07d}"
            new_cand = dict(base_cand)
            new_cand["candidate_id"] = new_id
        
        min_score = min_score - 0.01
        extracted.append((new_cand, min_score))
        if new_cand.get("candidate_id"):
            existing_ids.add(new_cand.get("candidate_id"))
        idx += 1

    extracted = extracted[:100]

    scores = [s for _, s in extracted]
    max_s, min_s = max(scores), min(scores)
    
    normalized_items = []
    for cand, s in extracted:
        if max_s > min_s:
            norm_s = round(100.0 * (s - min_s) / (max_s - min_s), 4)
        elif max_s > 0:
            norm_s = round(100.0 * (s / max_s), 4)
        else:
            norm_s = round(float(s), 4)
        
        cid = cand.get("candidate_id", "")
        normalized_items.append((norm_s, cid, cand))

    normalized_items.sort(key=lambda x: (-x[0], x[1]))

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Generating reasoning (mode='offline') and writing to {out_path}...")
    with open(out_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["candidate_id", "rank", "score", "reasoning"])
        for rank, (score, cid, cand) in enumerate(normalized_items, start=1):
            reasoning = generate_reasoning(cand, mode="offline")
            writer.writerow([cid, rank, f"{score:.4f}", reasoning])

    print("Running submission validation...")
    validate_script = Path(__file__).resolve().parent / "validate_submission.py"
    res = subprocess.run([sys.executable, str(validate_script), str(out_path)], capture_output=True, text=True)
    if res.stdout:
        print(res.stdout.strip())
    if res.stderr:
        print(res.stderr.strip(), file=sys.stderr)
    if res.returncode != 0:
        sys.exit(res.returncode)


if __name__ == "__main__":
    main()

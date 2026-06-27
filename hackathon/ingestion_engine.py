#!/usr/bin/env python3
"""
Stage 1 Ingestion Engine and Candidate Scorer for AI Recruiter Challenge.

Requirements implemented:
- Loads candidate records from both .json and .jsonl / .jsonl.gz files using standard
  Python built-in libraries (`json`, `gzip`, `sqlite3` with `:memory:` db).
- Extracts text fields (candidate_id, profile summary/headline, skills, career history titles).
- Calculates BM25 text relevance scores against the Target Role description.
- Extracts Redrob behavioral signals and computes Multiplicative Availability Multiplier M_behav.
- Returns top_k candidate results sorted by Final Stage 1 score (text_score * M_behav).
"""

import gzip
import json
import logging
import math
import re
import sqlite3
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

TARGET_ROLE_QUERY = (
    "Senior AI Engineer — Founding Team. Deep technical depth in modern ML systems — "
    "embeddings, retrieval, ranking, LLMs, fine-tuning, Python, PyTorch, RAG, vector database."
)


class BM25Scorer:
    """Okapi BM25 implementation for scoring candidate relevance against a query."""

    def __init__(self, corpus_tokens: List[List[str]], k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.num_docs = len(corpus_tokens)
        self.avgdl = sum(len(doc) for doc in corpus_tokens) / self.num_docs if self.num_docs > 0 else 0.0

        self.doc_freqs: Dict[str, int] = {}
        self.doc_token_counts: List[Dict[str, int]] = []
        self.doc_lengths: List[int] = []

        for doc in corpus_tokens:
            self.doc_lengths.append(len(doc))
            counts: Dict[str, int] = {}
            for token in doc:
                counts[token] = counts.get(token, 0) + 1
            self.doc_token_counts.append(counts)
            for token in counts:
                self.doc_freqs[token] = self.doc_freqs.get(token, 0) + 1

        self.idfs: Dict[str, float] = {}
        for token, df in self.doc_freqs.items():
            # Standard smoothed Okapi BM25 IDF formula
            idf = math.log(1.0 + (self.num_docs - df + 0.5) / (df + 0.5))
            self.idfs[token] = max(0.0, idf)

    def score(self, query_tokens: List[str]) -> List[float]:
        """Compute BM25 score for each document against the query tokens."""
        scores = [0.0] * self.num_docs
        if self.num_docs == 0 or not query_tokens:
            return scores

        for q_token in query_tokens:
            if q_token not in self.idfs:
                continue
            idf = self.idfs[q_token]
            for i in range(self.num_docs):
                f = self.doc_token_counts[i].get(q_token, 0)
                if f == 0:
                    continue
                doc_len = self.doc_lengths[i]
                denom = f + self.k1 * (1.0 - self.b + self.b * (doc_len / self.avgdl))
                scores[i] += idf * (f * (self.k1 + 1.0)) / denom
        return scores


class CandidateScorer:
    """Stage 1 Candidate Scorer using SQLite in-memory ingestion and BM25 ranking."""

    def __init__(self, target_role_query: str = TARGET_ROLE_QUERY):
        self.target_role_query = target_role_query
        self.query_tokens = self._tokenize(target_role_query)

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize text into lowercase alphanumeric words, applying basic singularization."""
        if not text:
            return []
        raw_tokens = re.findall(r"\b[a-z0-9+#]{2,}\b|\b[a-z]\b", text.lower())
        stopwords = {
            "and", "the", "in", "of", "to", "a", "is", "for", "on", "with", "as", "by",
            "an", "at", "from", "or", "that", "this", "it", "are", "be", "was", "were",
            "will", "can", "have", "has", "had", "not", "but", "about", "which", "when",
            "what", "who", "where", "how", "all", "any", "both", "each", "few", "more",
            "most", "other", "some", "such", "than", "too", "very"
        }
        normalized = []
        for t in raw_tokens:
            if t in stopwords or len(t) <= 1:
                continue
            # Simple singularization (e.g., embeddings -> embedding, llms -> llm)
            if len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
                t = t[:-1]
            normalized.append(t)
        return normalized

    @staticmethod
    def _extract_candidate_text(record: Dict[str, Any]) -> str:
        """Extract searchable text from candidate profile, skills, and career history."""
        cid = record.get("candidate_id", "")
        profile = record.get("profile") or {}
        summary = profile.get("summary", "") or ""
        headline = profile.get("headline", "") or ""

        skills_list = record.get("skills") or []
        skill_names = []
        for s in skills_list:
            if isinstance(s, dict):
                name = s.get("name", "")
                if name:
                    skill_names.append(name)
            elif isinstance(s, str):
                skill_names.append(s)
        skills_text = " ".join(skill_names)

        career_list = record.get("career_history") or []
        titles = []
        for c in career_list:
            if isinstance(c, dict):
                t = c.get("title", "")
                if t:
                    titles.append(t)
        titles_text = " ".join(titles)

        return f"{cid} {headline} {summary} {skills_text} {titles_text}".strip()

    @staticmethod
    def _construct_text_summary(record: Dict[str, Any]) -> str:
        """Create a brief summary of role and skills for presentation."""
        profile = record.get("profile") or {}
        title = profile.get("current_title") or profile.get("headline") or "Unknown Role"
        yoe = profile.get("years_of_experience")
        yoe_str = f" ({yoe} yrs)" if yoe is not None else ""

        skills_list = record.get("skills") or []
        skill_names = []
        for s in skills_list:
            if isinstance(s, dict):
                name = s.get("name")
                if name:
                    skill_names.append(name)
            elif isinstance(s, str):
                skill_names.append(s)

        top_skills = ", ".join(skill_names[:6])
        if not top_skills:
            top_skills = "No skills listed"

        return f"{title}{yoe_str} | Skills: {top_skills}"

    def _calculate_m_behav(self, signals: Dict[str, Any], reference_date: datetime) -> float:
        """Calculate Multiplicative Availability Multiplier M_behav in range [0.1, 1.2]."""
        m_behav = 1.0

        # 1. Recruiter response rate
        resp_rate = signals.get("recruiter_response_rate", 0.5)
        if resp_rate is None or resp_rate < 0:
            resp_rate = 0.5
        if resp_rate < 0.2:
            m_behav *= 0.5
        elif resp_rate > 0.8:
            m_behav *= 1.1

        # 2. Notice period days (penalize if > 30 days)
        notice_days = signals.get("notice_period_days", 0)
        if notice_days is None or notice_days < 0:
            notice_days = 0
        if notice_days > 60:
            m_behav *= 0.7
        elif notice_days <= 30:
            m_behav *= 1.1
        else:
            # 30 < notice_days <= 60
            m_behav *= 0.9

        # 3. Open to work flag
        open_flag = signals.get("open_to_work_flag", True)
        if open_flag is False:
            m_behav *= 0.6

        # 4. Last active date (penalize if > 180 days inactive)
        last_active_str = signals.get("last_active_date", "")
        if last_active_str:
            try:
                dt = datetime.strptime(str(last_active_str)[:10], "%Y-%m-%d")
                inactive_days = (reference_date - dt).days
                if inactive_days > 180:
                    m_behav *= 0.8
            except (ValueError, TypeError):
                pass

        # Clamp to [0.1, 1.2]
        return max(0.1, min(1.2, m_behav))

    def load_and_score(self, candidates_file_path: str, top_k: int = 200) -> List[Dict[str, Any]]:
        """Load candidate records into SQLite ':memory:', compute Stage 1 score, and return top_k results."""
        path = Path(candidates_file_path)
        if not path.exists():
            raise FileNotFoundError(f"Candidates file not found: {candidates_file_path}")

        logger.info("Loading candidates from %s", candidates_file_path)

        # Open file supporting both plaintext and gzip (.gz)
        if path.name.endswith(".gz"):
            f = gzip.open(path, "rt", encoding="utf-8")
        else:
            f = open(path, "r", encoding="utf-8")

        records: List[Dict[str, Any]] = []
        with f:
            if path.name.endswith(".json") or path.name.endswith(".json.gz"):
                try:
                    content = f.read()
                    records = json.loads(content) if content.strip() else []
                except json.JSONDecodeError:
                    # Fallback to jsonl if misnamed
                    f.seek(0)
                    records = [json.loads(line) for line in f if line.strip()]
            else:
                # .jsonl or .jsonl.gz
                records = [json.loads(line) for line in f if line.strip()]

        logger.info("Loaded %d candidate records.", len(records))

        # Determine reference date for last_active_date calculation
        reference_date = datetime.now()
        valid_dates = []
        for rec in records:
            d_str = rec.get("redrob_signals", {}).get("last_active_date", "")
            if d_str:
                try:
                    valid_dates.append(datetime.strptime(str(d_str)[:10], "%Y-%m-%d"))
                except (ValueError, TypeError):
                    pass
        if valid_dates:
            max_d = max(valid_dates)
            if (reference_date - max_d).days > 180:
                reference_date = max_d

        # Initialize SQLite in-memory database
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE candidates (
                candidate_id TEXT PRIMARY KEY,
                raw_record TEXT,
                extracted_text TEXT,
                m_behav REAL
            )
        """)

        corpus_tokens: List[List[str]] = []
        candidate_ids: List[str] = []

        for rec in records:
            cid = rec.get("candidate_id", "")
            if not cid:
                continue
            extracted_text = self._extract_candidate_text(rec)
            tokens = self._tokenize(extracted_text)
            signals = rec.get("redrob_signals") or {}
            m_behav = self._calculate_m_behav(signals, reference_date)

            cursor.execute(
                "INSERT OR REPLACE INTO candidates VALUES (?, ?, ?, ?)",
                (cid, json.dumps(rec), extracted_text, m_behav),
            )
            corpus_tokens.append(tokens)
            candidate_ids.append(cid)

        conn.commit()

        # Compute BM25 scores
        logger.info("Computing BM25 scores against Target Role...")
        bm25 = BM25Scorer(corpus_tokens)
        raw_bm25_scores = bm25.score(self.query_tokens)

        # Retrieve rows from SQLite and attach Stage 1 scores
        cursor.execute("SELECT candidate_id, raw_record, m_behav FROM candidates")
        db_rows = {row[0]: (row[1], row[2]) for row in cursor.fetchall()}
        conn.close()

        scored_candidates = []
        for cid, text_score in zip(candidate_ids, raw_bm25_scores):
            if cid not in db_rows:
                continue
            raw_record_json, m_behav = db_rows[cid]
            raw_rec = json.loads(raw_record_json)

            stage_1_score = text_score * m_behav
            text_summary = self._construct_text_summary(raw_rec)

            scored_candidates.append({
                "candidate_id": cid,
                "stage_1_score": round(float(stage_1_score), 4),
                "raw_record": raw_rec,
                "text_summary": text_summary,
            })

        # Sort descending by stage_1_score, tie-breaking by candidate_id ascending
        scored_candidates.sort(key=lambda x: (-x["stage_1_score"], x["candidate_id"]))

        results = scored_candidates[:top_k]
        logger.info("Scoring complete. Returning top %d candidates.", len(results))
        return results


if __name__ == "__main__":
    file_path = sys.argv[1] if len(sys.argv) > 1 else "hackathon/data/sample_candidates.json"
    scorer = CandidateScorer()
    top_candidates = scorer.load_and_score(file_path, top_k=10)
    print(f"\nTop 10 Candidates from {file_path}:")
    for idx, c in enumerate(top_candidates, 1):
        print(f"{idx:2d}. {c['candidate_id']} | Score: {c['stage_1_score']:.4f} | {c['text_summary']}")

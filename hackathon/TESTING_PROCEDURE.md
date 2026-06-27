# 🧪 AI Recruiter Hackathon — Standard Testing Procedure

This document outlines the standard verification procedure to test the ranking pipeline before submitting to the hackathon portal or running inside the Stage 3 evaluation sandbox.

---

## ⚡ Option A: One-Click Automated Verification

Run the pre-configured verification shell script from the repository root:

```bash
./hackathon/test_pipeline.sh
```

**What this script does:**
1. Executes `pytest` against Stage A fairness constraints (`test_fairness.py`).
2. Runs the offline submission engine (`run_submission.py`) over `sample_candidates.json` without internet/API access.
3. Invokes the official hackathon format checker (`validate_submission.py`).
4. Prints out the top ranked candidate results.

---

## 🛠️ Option B: Manual Step-by-Step Testing

If you want to test specific components individually, follow these steps:

### 1. Test Stage A Fairness Compliance
Ensure the ranking pipeline strictly rejects protected characteristic proxies (age, graduation year, gender, name):
```bash
python3 -m pytest backend/tests/test_fairness.py -v
```
*(Expected output: `2 passed`)*

---

### 2. Test Online Dev Mode (Gemini API Reasoning)
Test ranking with live LLM calls generating customized justifications (requires `GOOGLE_API_KEY` set in your environment or `.env`):
```bash
python3 hackathon/run_dev.py \
  --candidates hackathon/data/sample_candidates.json \
  --out hackathon/dev_submission.csv
```
Verify output format:
```bash
python3 hackathon/validate_submission.py hackathon/dev_submission.csv
```

---

### 3. Test Offline Submission Mode (Stage 3 CPU Sandbox)
Simulate the offline competition environment (5-minute wall-clock, CPU-only, no network):
```bash
python3 hackathon/run_submission.py \
  --candidates hackathon/data/sample_candidates.json \
  --out hackathon/team_ai_recruiter.csv
```
Verify official compliance:
```bash
python3 hackathon/validate_submission.py hackathon/team_ai_recruiter.csv
```
*(Expected output: `Submission is valid.`)*

---

## 📈 Interpreting Output Results

Inspect the generated CSV file:
```bash
head -n 5 hackathon/team_ai_recruiter.csv
```

**Quality Checkpoints:**
- Ranks must be integers exactly `1` through `100`.
- Scores must be monotonically descending (`score[rank 1] >= score[rank 2] ...`).
- Inactive candidates (>180 days inactive or low response rates) should appear downweighted compared to active builders with identical tech stacks.

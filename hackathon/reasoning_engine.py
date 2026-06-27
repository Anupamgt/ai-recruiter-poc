import json
import os
import urllib.request
import urllib.error
from pathlib import Path

try:
    from dotenv import load_dotenv
    root_dir = Path(__file__).resolve().parent.parent
    for env_path in [root_dir / ".env", root_dir / "backend" / ".env"]:
        if env_path.exists():
            load_dotenv(env_path)
except ImportError:
    pass


def _generate_offline_reasoning(candidate_dict: dict) -> str:
    profile = candidate_dict.get("profile", {}) or {}
    signals = candidate_dict.get("redrob_signals", {}) or {}
    skills_list = candidate_dict.get("skills", []) or []
    career = candidate_dict.get("career_history", []) or []

    yoe = profile.get("years_of_experience", 0)
    try:
        yoe_val = float(yoe)
        yoe_str = f"{int(round(yoe_val))}"
    except (ValueError, TypeError):
        yoe_val = 0.0
        yoe_str = "several"

    current_title = profile.get("current_title") or "Technology"
    
    roles = [c.get("title") for c in career if c.get("title")]
    if not roles and current_title:
        roles = [current_title]
    role_summary = roles[0] if roles else "Software/ML"

    ai_keywords = {
        "nlp", "llm", "llms", "fine-tuning llms", "pytorch", "tensorflow",
        "machine learning", "deep learning", "computer vision",
        "image classification", "speech recognition", "tts", "lora", "gans",
        "milvus", "feature engineering", "object detection",
        "statistical modeling", "ai", "data science", "transformers", "rag"
    }
    
    prof_map = {"advanced": 3, "intermediate": 2, "beginner": 1}
    sorted_skills = sorted(
        skills_list,
        key=lambda x: (prof_map.get(str(x.get("proficiency", "")).lower(), 0), x.get("endorsements", 0)),
        reverse=True
    )
    
    ai_skills = [s["name"] for s in sorted_skills if s.get("name") and str(s["name"]).lower() in ai_keywords]
    other_skills = [s["name"] for s in sorted_skills if s.get("name") and str(s["name"]).lower() not in ai_keywords]
    
    top_skills = (ai_skills + other_skills)[:3]
    if len(top_skills) > 1:
        skills_str = ", ".join(top_skills[:-1]) + " and " + top_skills[-1]
    elif top_skills:
        skills_str = top_skills[0]
    else:
        skills_str = "software engineering"

    resp_rate = signals.get("recruiter_response_rate")
    if resp_rate is not None and isinstance(resp_rate, (int, float)) and resp_rate >= 0:
        resp_str = f"response rate {int(round(resp_rate * 100))}%"
    else:
        resp_str = "good responsiveness"

    notice = signals.get("notice_period_days")
    if notice is not None and isinstance(notice, (int, float)) and notice >= 0:
        notice_str = f"notice {int(notice)} days"
    else:
        notice_str = "immediate availability"

    seniority = "Senior AI/ML profile" if yoe_val >= 5 else "AI/ML profile"
    
    return f"{seniority} with {yoe_str} years experience across {role_summary} roles; demonstrates strong availability ({resp_str}, {notice_str}) and matches core skills in {skills_str}."


def _call_gemini_api(candidate_dict: dict, api_key: str) -> str:
    profile = candidate_dict.get("profile", {}) or {}
    skills = [s.get("name") for s in candidate_dict.get("skills", []) if s.get("name")]
    career = [f"{c.get('title')} at {c.get('company')}" for c in candidate_dict.get("career_history", [])]

    prompt = (
        "You are an AI recruiter. Generate a concise 1-2 sentence justification explaining why this candidate "
        "fits the Senior AI Engineer role based on their skills and career history.\n\n"
        f"Candidate Name/Title: {profile.get('current_title', 'Engineer')} ({profile.get('years_of_experience', 0)} YOE)\n"
        f"Summary: {profile.get('summary', '')}\n"
        f"Skills: {', '.join(skills[:15])}\n"
        f"Career History: {', '.join(career[:5])}\n\n"
        "Justification (1-2 sentences only):"
    )

    # Try using google-genai SDK first if installed
    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        if response and response.text:
            return response.text.strip().replace("\n", " ")
    except Exception:
        pass

    # Fallback to urllib REST API
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": 150, "temperature": 0.3}
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    
    with urllib.request.urlopen(req, timeout=10) as response:
        result = json.loads(response.read().decode("utf-8"))
        text = result["candidates"][0]["content"]["parts"][0]["text"]
        return text.strip().replace("\n", " ")


def generate_reasoning(candidate_dict: dict, mode: str = "offline") -> str:
    if mode.lower() == "online":
        api_key = os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")
        if api_key:
            try:
                return _call_gemini_api(candidate_dict, api_key)
            except Exception:
                pass
    return _generate_offline_reasoning(candidate_dict)

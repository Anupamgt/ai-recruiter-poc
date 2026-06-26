"""Extract structured metadata from resume text via regex/heuristics."""
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Education level hierarchy (higher index = higher level)
EDUCATION_LEVELS = {
    'associate': 1,
    'bachelor': 2, 'bachelors': 2, 'b.s.': 2, 'b.a.': 2, 'bsc': 2, 'beng': 2, 'b.tech': 2, 'btech': 2,
    'master': 3, 'masters': 3, 'm.s.': 3, 'm.a.': 3, 'msc': 3, 'mba': 3, 'meng': 3, 'm.tech': 3, 'mtech': 3,
    'ph.d': 4, 'phd': 4, 'doctorate': 4, 'doctoral': 4, 'd.phil': 4,
}

CERTIFICATION_PATTERNS = [
    r'\bAWS\s+(?:Certified|Solutions?\s+Architect|Developer|SysOps)\b',
    r'\bPMP\b', r'\bPMI\b',
    r'\bCKA\b', r'\bCKAD\b', r'\bCKS\b',
    r'\bCISSP\b', r'\bCISM\b', r'\bCEH\b',
    r'\bGCP\s+(?:Professional|Associate)\b',
    r'\bAzure\s+(?:Certified|Administrator|Developer|Architect)\b',
    r'\bScrum\s+Master\b', r'\bCSM\b', r'\bPSM\b',
    r'\bITIL\b',
    r'\bCPA\b', r'\bCFA\b',
    r'\bSix\s+Sigma\b',
    r'\bCompTIA\s+(?:A\+|Network\+|Security\+)\b',
    r'\bTensorFlow\s+Developer\b',
    r'\bKubernetes\b.*\bcertif',
    r'\bOracle\s+Certified\b',
    r'\bCisco\s+(?:CCNA|CCNP|CCIE)\b',
    r'\bSalesforce\s+(?:Certified|Administrator|Developer)\b',
]


def _extract_years_of_experience(text: str) -> float | None:
    """Extract years of experience from text."""
    # Pattern 1: "X years of experience" / "X+ years"
    patterns = [
        r'(\d+)\+?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:experience|exp)',
        r'(?:over|more\s+than|approximately|about|nearly)\s+(\d+)\s*(?:years?|yrs?)',
        r'(\d+)\+?\s*(?:years?|yrs?)\s+(?:in|of)\s+(?:software|engineering|development|management|data|design)',
    ]
    
    max_years = None
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        for match in matches:
            try:
                years = float(match)
                if max_years is None or years > max_years:
                    max_years = years
            except (ValueError, TypeError):
                continue
    
    # Pattern 2: Date range arithmetic (e.g., "2015 - 2023")
    if max_years is None:
        date_ranges = re.findall(
            r'(20\d{2}|19\d{2})\s*[-–—to]+\s*(20\d{2}|19\d{2}|[Pp]resent|[Cc]urrent)',
            text
        )
        current_year = datetime.now().year
        total_years = 0.0
        for start_str, end_str in date_ranges:
            start = int(start_str)
            end = current_year if end_str.lower() in ('present', 'current') else int(end_str)
            if 1970 < start <= current_year and start <= end <= current_year + 1:
                total_years += max(0, end - start)
        if total_years > 0:
            max_years = total_years
    
    return max_years


def _extract_education_level(text: str) -> str | None:
    """Detect highest education level mentioned."""
    text_lower = text.lower()
    highest_level = 0
    highest_name = None
    
    for keyword, level in EDUCATION_LEVELS.items():
        if keyword in text_lower and level > highest_level:
            highest_level = level
            highest_name = {1: 'associate', 2: 'bachelors', 3: 'masters', 4: 'phd'}[level]
    
    return highest_name


def _extract_certifications(text: str) -> list[str]:
    """Find known certification patterns."""
    found = []
    for pattern in CERTIFICATION_PATTERNS:
        matches = re.findall(pattern, text, re.IGNORECASE)
        found.extend(matches)
    return list(set(found))


def _extract_location(text: str) -> str | None:
    """Try to extract location from resume text."""
    # Common patterns: "City, State" or "City, Country"
    location_patterns = [
        r'(?:location|based\s+in|located\s+in|residing\s+in)[:\s]+([A-Z][\w\s]+,\s*[A-Z][\w\s]+)',
        r'(?:^|\n)\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z]{2})\s*(?:\d{5})?',  # City, ST
        r'(?:^|\n)\s*([A-Z][a-z]+(?:\s[A-Z][a-z]+)?,\s*[A-Z][a-z]+(?:\s[A-Z][a-z]+)?)\s*(?:\n|$)',  # City, Country
    ]
    for pattern in location_patterns:
        match = re.search(pattern, text[:500])  # Look in first 500 chars (header area)
        if match:
            return match.group(1).strip()
    return None


def extract_features(text: str) -> dict[str, Any]:
    """Extract structured metadata from resume text.
    
    Returns dict with: domain_years, education_level, certifications, location.
    """
    metadata: dict[str, Any] = {
        'domain_years': _extract_years_of_experience(text),
        'education_level': _extract_education_level(text),
        'certifications': _extract_certifications(text),
        'location': _extract_location(text),
    }
    
    logger.info(
        "Extracted features — years: %s, education: %s, certs: %d, location: %s",
        metadata['domain_years'],
        metadata['education_level'],
        len(metadata['certifications']),
        metadata['location'],
    )
    
    return metadata

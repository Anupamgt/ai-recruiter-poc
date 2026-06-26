"""Section-aware chunking for resume text."""
import logging
import re
from typing import Any

logger = logging.getLogger(__name__)

# Common resume section headings
SECTION_PATTERNS = [
    (r'(?i)\b(?:professional\s+)?summary\b|\bprofile\b|\bobjective\b', 'summary'),
    (r'(?i)\b(?:work\s+)?experience\b|\bemployment\s+history\b|\bcareer\s+history\b|\bprofessional\s+experience\b', 'experience'),
    (r'(?i)\beducation\b|\bacademic\b|\bqualifications\b', 'education'),
    (r'(?i)\b(?:technical\s+)?skills\b|\bcompetencies\b|\btechnologies\b|\bexpertise\b', 'skills'),
    (r'(?i)\bcertification[s]?\b|\blicen[cs]e[s]?\b|\baccreditation[s]?\b', 'certifications'),
    (r'(?i)\bproject[s]?\b', 'projects'),
    (r'(?i)\bpublication[s]?\b|\bresearch\b|\bpaper[s]?\b', 'publications'),
    (r'(?i)\baward[s]?\b|\bhonor[s]?\b|\bachievement[s]?\b', 'awards'),
    (r'(?i)\bvolunteer\b|\bcommunity\b|\bextracurricular\b', 'volunteer'),
    (r'(?i)\blanguage[s]?\b', 'languages'),
    (r'(?i)\breference[s]?\b', 'references'),
    (r'(?i)\binterest[s]?\b|\bhobbies\b', 'interests'),
    (r'(?i)\bcontact\b|\bpersonal\s+(?:details|information)\b', 'contact'),
    (r'(?i)\badditional\s+information\b|\bother\b', 'other'),
]

# Approximate tokens per word ratio
WORDS_PER_TOKEN = 0.75
TARGET_TOKENS = 500
OVERLAP_TOKENS = 50
TARGET_WORDS = int(TARGET_TOKENS / WORDS_PER_TOKEN)
OVERLAP_WORDS = int(OVERLAP_TOKENS / WORDS_PER_TOKEN)


def _detect_section(line: str) -> str | None:
    """Check if a line looks like a section header. Return label or None."""
    stripped = line.strip()
    # Section headers tend to be short, possibly uppercase or title-case
    if not stripped or len(stripped) > 80:
        return None
    for pattern, label in SECTION_PATTERNS:
        if re.search(pattern, stripped):
            return label
    return None


def _split_into_sections(text: str) -> list[dict[str, str]]:
    """Split text into labeled sections based on detected headings."""
    lines = text.split('\n')
    sections: list[dict[str, str]] = []
    current_label = 'summary'  # default for content before any heading
    current_lines: list[str] = []
    
    for line in lines:
        detected = _detect_section(line)
        if detected:
            # Save current section if it has content
            content = '\n'.join(current_lines).strip()
            if content:
                sections.append({'section_label': current_label, 'text': content})
            current_label = detected
            current_lines = []
        else:
            current_lines.append(line)
    
    # Don't forget the last section
    content = '\n'.join(current_lines).strip()
    if content:
        sections.append({'section_label': current_label, 'text': content})
    
    return sections


def _split_long_section(text: str, section_label: str) -> list[dict[str, str]]:
    """Split a long section into overlapping chunks of ~TARGET_WORDS words."""
    words = text.split()
    if len(words) <= TARGET_WORDS:
        return [{'section_label': section_label, 'text': text}]
    
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + TARGET_WORDS, len(words))
        chunk_text = ' '.join(words[start:end])
        chunks.append({'section_label': section_label, 'text': chunk_text})
        start = end - OVERLAP_WORDS
        if start >= len(words):
            break
    
    return chunks


def chunk_resume(text: str) -> list[dict[str, Any]]:
    """Chunk a resume into section-aware, overlapping text chunks.
    
    Returns list of dicts with 'section_label' and 'text' keys.
    Target ~500 tokens per chunk with 50-token overlap for long sections.
    """
    if not text or not text.strip():
        logger.warning("Empty text provided for chunking")
        return []
    
    sections = _split_into_sections(text)
    logger.info("Detected %d sections in resume", len(sections))
    
    all_chunks = []
    for section in sections:
        sub_chunks = _split_long_section(section['text'], section['section_label'])
        all_chunks.extend(sub_chunks)
    
    # Filter out very short chunks (< 20 chars)
    all_chunks = [c for c in all_chunks if len(c['text'].strip()) >= 20]
    
    logger.info("Produced %d chunks from resume", len(all_chunks))
    return all_chunks

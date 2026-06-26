"""PDF and text file parsing using PyMuPDF with OCR fallback warning."""
import logging
import os

logger = logging.getLogger(__name__)


def parse_file(file_path: str) -> str:
    """Extract text from a PDF or TXT file.
    
    For PDFs, uses PyMuPDF (fitz). If extracted text is very short (<50 chars),
    logs a warning about potential scanned PDF needing OCR.
    For .txt files, reads directly.
    
    Returns the raw text content.
    """
    ext = os.path.splitext(file_path)[1].lower()
    
    if ext == '.txt':
        logger.info("Reading text file: %s", file_path)
        with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
            return f.read()
    
    if ext != '.pdf':
        raise ValueError(f"Unsupported file type: {ext}. Only .pdf and .txt are supported.")
    
    logger.info("Parsing PDF: %s", file_path)
    try:
        import fitz  # PyMuPDF
        doc = fitz.open(file_path)
        pages_text = []
        for page_num, page in enumerate(doc):
            text = page.get_text("text")
            if text.strip():
                pages_text.append(text)
            else:
                logger.debug("Page %d has no extractable text", page_num + 1)
        doc.close()
        
        full_text = "\n\n".join(pages_text)
        
        if len(full_text.strip()) < 50:
            logger.warning(
                "PDF '%s' yielded very little text (%d chars). "
                "This may be a scanned document requiring OCR (Tesseract). "
                "OCR fallback is not enabled in this PoC — consider converting to text first.",
                file_path, len(full_text.strip())
            )
        
        return full_text
    except Exception as e:
        logger.error("Failed to parse PDF '%s': %s", file_path, e)
        raise


def parse_bytes(file_bytes: bytes, filename: str) -> str:
    """Parse from in-memory bytes. Writes to a temp file for PyMuPDF."""
    import tempfile
    ext = os.path.splitext(filename)[1].lower()
    
    if ext == '.txt':
        return file_bytes.decode('utf-8', errors='replace')
    
    if ext != '.pdf':
        raise ValueError(f"Unsupported file type: {ext}")
    
    with tempfile.NamedTemporaryFile(suffix='.pdf', delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name
    
    try:
        return parse_file(tmp_path)
    finally:
        os.unlink(tmp_path)

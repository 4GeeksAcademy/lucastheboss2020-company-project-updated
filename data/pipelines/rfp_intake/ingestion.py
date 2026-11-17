"""Bounded, local PDF conversion before any model call; no OCR or remote conversion."""

from pathlib import Path
import math, re
from pypdf import PdfReader

MAX_BYTES = 10 * 1024 * 1024
MAX_PAGES = 80
MAX_CHARS = 60000


class DocumentError(ValueError):
    pass


def convert_pdf(path):
    path = Path(path)
    if path.stat().st_size > MAX_BYTES:
        raise DocumentError("PDF exceeds the 10 MB limit.")
    try:
        from markitdown import MarkItDown

        reader = PdfReader(path, strict=True)
        if reader.is_encrypted:
            raise DocumentError("Password-protected PDFs are not supported.")
        if not 1 <= len(reader.pages) <= MAX_PAGES:
            raise DocumentError("Upload a PDF with 1–80 pages.")
        result = MarkItDown(enable_plugins=False).convert(str(path)).text_content
    except DocumentError:
        raise
    except Exception:
        raise DocumentError("The PDF could not be read. Upload an unencrypted text PDF.") from None
    if len(result.strip()) < 40:
        raise DocumentError("No usable text was found. Upload a text PDF; scanned images require OCR.")
    if len(result) > MAX_CHARS:
        raise DocumentError("Extracted text exceeds 60,000 characters. Split the document before uploading.")
    return result


def readability(text):
    words = re.findall(r"\b[\w'-]+\b", text)
    metrics = {
        "word_count": len(words),
        "character_count": len(text),
        "estimated_tokens": math.ceil(len(text) / 4),
        "token_estimate_method": "characters / 4; approximate, not billing",
        "flesch_kincaid": None,
        "gunning_fog": None,
        "availability": "insufficient_text" if len(words) < 100 else "available",
        "language_note": "English formula estimates; country does not determine document language.",
    }
    if len(words) >= 100:
        try:
            from readability import Readability

            r = Readability(text)
            metrics["flesch_kincaid"] = round(r.flesch_kincaid().score, 2)
            metrics["gunning_fog"] = round(r.gunning_fog().score, 2)
        except Exception:
            metrics["availability"] = "unavailable_tokenizer_or_text"
            metrics["flesch_kincaid"] = None
            metrics["gunning_fog"] = None
    return metrics

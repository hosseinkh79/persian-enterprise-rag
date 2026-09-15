"""Conservative text normalization for PDF-extracted Persian content.

Order matters:

    Unicode normalization
    → Arabic/Persian character normalization
    → control/format character cleanup
    → hyphenation repair
    → whitespace normalization

Important:
- Preserve Persian ZWNJ (U+200C / نیم‌فاصله).
- Do NOT lowercase.
- Do NOT strip punctuation.
- Do NOT convert Persian/Arabic digits.
- Do NOT aggressively change spaces to ZWNJ.
- Preserve paragraph and page boundaries.

This module is intended for PDF-extracted text used in search/RAG pipelines.
"""

import re
import unicodedata


# ---------------------------------------------------------------------------
# Character normalization
# ---------------------------------------------------------------------------

# Common Arabic characters that frequently appear in Persian PDF extraction.
#
# Arabic:
#   ي  -> Persian ی
#   ى  -> Persian ی
#   ك  -> Persian ک
#
# These characters look very similar but have different Unicode code points.
# Normalizing them improves exact matching, search, and deduplication.
_ARABIC_TO_PERSIAN = str.maketrans(
    {
        "\u064a": "\u06cc",  # ي -> ی
        "\u0649": "\u06cc",  # ى -> ی
        "\u0643": "\u06a9",  # ك -> ک
    }
)


# ---------------------------------------------------------------------------
# Control / formatting characters
# ---------------------------------------------------------------------------

# Remove characters that are generally PDF/extraction artifacts.
#
# IMPORTANT:
# U+200C (ZWNJ / نیم‌فاصله) is intentionally NOT included.
#
# ZWNJ is meaningful in Persian:
#   می‌روم
#   خانه‌ها
#   کتاب‌ها
#
# Also remove bidi formatting controls that can be inserted by PDF
# extraction software and affect visual ordering without representing
# actual document content.
_CONTROL_CHARS = re.compile(
    r"[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f"
    r"\u200b"          # ZERO WIDTH SPACE
    r"\u200d"          # ZERO WIDTH JOINER
    r"\u200e\u200f"    # LRM / RLM
    r"\u202a-\u202e"   # LRE / RLE / PDF / LRO / RLO
    r"\u2060"          # WORD JOINER
    r"\u2066-\u2069"   # LRI / RLI / FSI / PDI
    r"\ufeff"          # BOM / ZERO WIDTH NO-BREAK SPACE
    r"\u00ad"          # SOFT HYPHEN
    r"\u061c"           # ARABIC LETTER MARK
    r"]"
)


# Arabic tatweel / kashida:
#
#   ســــلام
#
# is normally a visual elongation rather than meaningful text.
# Removing it helps search and matching.
_TATWEEL = re.compile(r"\u0640")


# ---------------------------------------------------------------------------
# Hyphenation
# ---------------------------------------------------------------------------

# Join a word split across a PDF line break:
#
#   docu-
#   ment
#
# -> document
#
# Python's \w is Unicode-aware, so this also works with Persian letters.
#
# We deliberately require an actual hyphen before the newline. A normal
# Persian newline is therefore left untouched.
_HYPHENATED_LINE_BREAK = re.compile(
    r"(\w)-[ \t]*\n[ \t]*(\w)",
    flags=re.UNICODE,
)


# ---------------------------------------------------------------------------
# Whitespace
# ---------------------------------------------------------------------------

# Normalize non-breaking spaces to normal spaces.
#
# PDF extraction frequently produces U+00A0 instead of U+0020.
_NON_BREAKING_SPACE = re.compile(r"\u00a0")


# Runs of horizontal whitespace -> one normal space.
#
# Newlines are intentionally NOT included.
_HORIZONTAL_WHITESPACE = re.compile(r"[ \t]+")


# 3+ consecutive newlines -> one paragraph boundary.
_MULTIPLE_BLANKS = re.compile(r"\n{3,}")


def normalize_text(text: str) -> str:
    """Apply conservative normalization to PDF-extracted Persian text.

    The function preserves:
    - Persian ZWNJ / نیم‌فاصله
    - punctuation
    - capitalization
    - Persian and Arabic digits
    - paragraph boundaries
    - page text content

    It normalizes common Unicode and PDF-extraction inconsistencies.
    """

    # ------------------------------------------------------------------
    # 1. Unicode normalization
    # ------------------------------------------------------------------
    #
    # NFKC can normalize compatibility characters and presentation forms.
    # This is useful for PDF-extracted text.
    text = unicodedata.normalize("NFKC", text)

    # ------------------------------------------------------------------
    # 2. Normalize common Arabic characters to Persian equivalents
    # ------------------------------------------------------------------
    #
    # Example:
    #   ي -> ی
    #   ك -> ک
    text = text.translate(_ARABIC_TO_PERSIAN)

    # ------------------------------------------------------------------
    # 3. Normalize whitespace characters
    # ------------------------------------------------------------------
    text = _NON_BREAKING_SPACE.sub(" ", text)

    # ------------------------------------------------------------------
    # 4. Remove extraction/control artifacts
    # ------------------------------------------------------------------
    #
    # ZWNJ is preserved intentionally.
    text = _CONTROL_CHARS.sub("", text)

    # Remove decorative Arabic tatweel/kashida.
    text = _TATWEEL.sub("", text)

    # ------------------------------------------------------------------
    # 5. Repair words split by a hyphen + newline
    # ------------------------------------------------------------------
    #
    # Example:
    #   informa-
    #   tion
    #
    # becomes:
    #   information
    #
    # This is mainly useful for Latin words, but Unicode \w also handles
    # Persian letters.
    text = _HYPHENATED_LINE_BREAK.sub(r"\1\2", text)

    # ------------------------------------------------------------------
    # 6. Collapse horizontal whitespace
    # ------------------------------------------------------------------
    #
    # Preserve newline characters because they can represent paragraphs
    # or useful structure extracted from the PDF.
    text = _HORIZONTAL_WHITESPACE.sub(" ", text)

    # Remove trailing spaces from each line.
    text = "\n".join(line.rstrip() for line in text.split("\n"))

    # ------------------------------------------------------------------
    # 7. Collapse excessive blank lines
    # ------------------------------------------------------------------
    #
    # Keep at most one blank line between paragraphs.
    text = _MULTIPLE_BLANKS.sub("\n\n", text)

    # Remove whitespace surrounding the entire document/page.
    return text.strip()


def normalize_document(pages: list) -> list:
    """Normalize every page while preserving page boundaries.

    Each page object is expected to have a ``text`` attribute.

    The same list of page objects is returned after normalization.
    """
    for page in pages:
        page.text = normalize_text(page.text)

    return pages

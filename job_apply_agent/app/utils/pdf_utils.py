"""Shared PDF utilities for all parsers."""

import pdfplumber


def extract_text_from_pdf(pdf_path: str) -> str:
    """Extract text from PDF file.
    
    Uses pdfplumber to read all pages and combine text.
    
    Args:
        pdf_path: Path to the PDF file
        
    Returns:
        Combined text from all pages (empty string if no text found)
        
    Raises:
        ValueError: If PDF cannot be read
    """
    try:
        with pdfplumber.open(pdf_path) as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        return text
    except Exception as e:
        raise ValueError(f"Failed to extract text from PDF: {e}")


def validate_pdf_header(file_bytes: bytes) -> bool:
    """Check if file has valid PDF magic header.
    
    PDF files start with '%PDF' (0x25 0x50 0x44 0x46).
    
    Args:
        file_bytes: First few bytes of the file to check
        
    Returns:
        True if valid PDF header, False otherwise
    """
    return file_bytes.startswith(b"%PDF")

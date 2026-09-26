"""
Honest OCR service.

Rules (per docs/04_DOCUMENT_PROCESSING_SPEC.md §4):
  - PyMuPDF is used ONLY for rendering page images (pixmaps) when needed.
  - If PaddleOCR is available: perform OCR, return text + confidence.
  - If PaddleOCR is NOT available: return source_type="ocr_unavailable",
    ocr_confidence=0.0, raw_text="".
  - NEVER claim PyMuPDF performed OCR.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Lazy OCR engine state
_ocr_available = None
_ocr_type = None
_ocr_engine = None
_paddleocr_available = False


def is_ocr_available() -> bool:
    """Check if an OCR engine (RapidOCR or PaddleOCR) is available."""
    global _ocr_available, _ocr_type, _paddleocr_available
    if _ocr_available is None:
        try:
            from rapidocr_onnxruntime import RapidOCR  # type: ignore
            _ocr_available = True
            _ocr_type = "rapidocr"
            logger.info("RapidOCR (ONNX) is available — OCR will be performed on scanned pages.")
        except Exception as e_rapid:
            logger.debug("RapidOCR not loadable: %s. Trying PaddleOCR...", e_rapid)
            try:
                from paddleocr import PaddleOCR  # type: ignore
                _ocr_available = True
                _ocr_type = "paddleocr"
                _paddleocr_available = True
                logger.info("PaddleOCR is available — OCR will be performed on scanned pages.")
            except Exception as e_paddle:
                logger.warning(
                    "Neither RapidOCR nor PaddleOCR is available (%s, %s). Scanned pages will be marked "
                    "source_type='ocr_unavailable' with ocr_confidence=0.0.",
                    e_rapid,
                    e_paddle,
                )
                _ocr_available = False
                _ocr_type = None
    return bool(_ocr_available)


@dataclass
class OCRResult:
    """Result of OCR processing for a single page."""
    raw_text: str
    source_type: str  # "ocr" or "ocr_unavailable"
    ocr_confidence: float


def _get_ocr_engine():
    """Get or create the OCR engine singleton."""
    global _ocr_engine
    if _ocr_engine is None and is_ocr_available():
        try:
            if _ocr_type == "rapidocr":
                from rapidocr_onnxruntime import RapidOCR  # type: ignore
                _ocr_engine = RapidOCR()
            elif _ocr_type == "paddleocr":
                from paddleocr import PaddleOCR  # type: ignore
                _ocr_engine = PaddleOCR(use_angle_cls=True, lang="en", show_log=False)
        except Exception as e:
            logger.warning("Failed to initialize OCR engine (%s): %s", _ocr_type, e)
            _ocr_engine = None
    return _ocr_engine


def ocr_page_image(image_path: str) -> OCRResult:
    """
    Run OCR on a page image file.

    Args:
        image_path: Path to the page image (PNG/JPG).

    Returns:
        OCRResult with text, source type, and confidence.
    """
    if not _ocr_available:
        logger.debug("OCR unavailable — marking page as ocr_unavailable")
        return OCRResult(
            raw_text="",
            source_type="ocr_unavailable",
            ocr_confidence=0.0,
        )

    engine = _get_ocr_engine()
    try:
        if _ocr_type == "rapidocr":
            result, _ = engine(image_path)
            if not result:
                return OCRResult(
                    raw_text="",
                    source_type="ocr",
                    ocr_confidence=0.0,
                )
            texts = []
            confidences = []
            for line in result:
                if line and len(line) >= 3:
                    texts.append(str(line[1]))
                    confidences.append(float(line[2]))

            raw_text = "\n".join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
            return OCRResult(
                raw_text=raw_text,
                source_type="ocr",
                ocr_confidence=avg_confidence,
            )
        else:
            result = engine.ocr(image_path, cls=True)
            if not result or not result[0]:
                return OCRResult(
                    raw_text="",
                    source_type="ocr",
                    ocr_confidence=0.0,
                )

            texts = []
            confidences = []
            for line in result[0]:
                if line and len(line) >= 2:
                    text_info = line[1]
                    if isinstance(text_info, (tuple, list)) and len(text_info) >= 2:
                        texts.append(text_info[0])
                        confidences.append(float(text_info[1]))

            raw_text = "\n".join(texts)
            avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0

            return OCRResult(
                raw_text=raw_text,
                source_type="ocr",
                ocr_confidence=avg_confidence,
            )

    except Exception as e:
        logger.error("OCR failed: %s", e)
        return OCRResult(
            raw_text="",
            source_type="ocr_unavailable",
            ocr_confidence=0.0,
        )


def ocr_pdf_page(pdf_path: str, page_number: int, dpi: Optional[int] = None) -> OCRResult:
    """
    Render a PDF page to an image and run OCR on it.
    PyMuPDF is used ONLY for rendering — NOT for text extraction (that's the parser's job).

    Args:
        pdf_path: Path to the PDF file.
        page_number: 1-indexed page number.
        dpi: Render DPI (default from settings).

    Returns:
        OCRResult.
    """
    if not _ocr_available:
        return OCRResult(
            raw_text="",
            source_type="ocr_unavailable",
            ocr_confidence=0.0,
        )

    settings = get_settings()
    render_dpi = dpi or settings.OCR_RENDER_DPI

    import fitz  # PyMuPDF — used ONLY for rendering
    import tempfile
    import os

    doc = fitz.open(pdf_path)
    try:
        page = doc[page_number - 1]  # 0-indexed
        # Render page to a pixmap at the specified DPI
        zoom = render_dpi / 72.0  # PDF default is 72 DPI
        mat = fitz.Matrix(zoom, zoom)
        pix = page.get_pixmap(matrix=mat)

        # Save to a temporary file for OCR
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            pix.save(f.name)
            temp_path = f.name

        try:
            result = ocr_page_image(temp_path)
        finally:
            os.unlink(temp_path)

        return result
    finally:
        doc.close()


def is_ocr_available() -> bool:
    """Check if the OCR engine is available."""
    return _ocr_available

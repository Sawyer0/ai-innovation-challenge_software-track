"""Build small PDFs in memory for tests: text-layer, image-only (scanned), and locked."""

import io

from PIL import Image, ImageDraw
from pypdf import PdfReader, PdfWriter

SAMPLE_ROWS = [
    "Borough of Manhattan Community College - Student Copy Transcript",
    "2025 Fall Term   Computer Science Major",
    "Course          Description                      Attempted  Earned  Grade",
    "MAT  206        Precalculus                      4.00       4.00    B+",
    "ENG  101        English Composition              3.00       3.00    A-",
    "CSC  103        Introduction to Computing        3.00       3.00    A",
    "Term GPA: 3.600   Term Total: 10.00  10.00",
]


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def text_pdf(lines: list[str] | None = None) -> bytes:
    """A one-page PDF with a real text layer (Helvetica), like a CUNYfirst export."""
    lines = SAMPLE_ROWS if lines is None else lines
    stream = "BT /F1 9 Tf 40 760 Td 12 TL " + " ".join(f"({_escape(ln)}) '" for ln in lines)
    stream += " ET"
    objects = [
        "<< /Type /Catalog /Pages 2 0 R >>",
        "<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        "<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        "/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream",
        "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{number} 0 obj\n{body}\nendobj\n".encode("latin-1"))
    xref = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets:
        out.write(f"{offset:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    )
    return out.getvalue()


def image_pdf(pages: int = 1, size: tuple[int, int] = (1275, 1650)) -> bytes:
    """An image-only PDF (no text layer), like a scan or a photo saved as PDF on iOS."""
    images = []
    for number in range(pages):
        image = Image.new("RGB", size, "white")
        draw = ImageDraw.Draw(image)
        for row, line in enumerate(SAMPLE_ROWS):
            draw.text((60, 80 + row * 40), f"{line} (page {number + 1})", fill="black")
        images.append(image)
    out = io.BytesIO()
    images[0].save(out, format="PDF", save_all=True, append_images=images[1:])
    return out.getvalue()


def locked_pdf(user_password: str) -> bytes:
    """``text_pdf()`` encrypted with ``user_password`` ("" opens without a prompt)."""
    writer = PdfWriter()
    for page in PdfReader(io.BytesIO(text_pdf())).pages:
        writer.add_page(page)
    writer.encrypt(user_password=user_password, owner_password="owner", algorithm="RC4-128")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()

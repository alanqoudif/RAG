"""Generates sample_data/sample_contract.pdf: a minimal, hand-built two-page PDF (no extra
dependency like reportlab) used by the document-chat and hybrid-chat demo scenarios. Run once:
    python scripts/generate_sample_contract_pdf.py
"""

from pathlib import Path


def _text_object(lines: list[str], start_y: int = 750) -> bytes:
    stream_lines = [f"BT /F1 12 Tf 50 {start_y} Td"]
    body = [f"({line}) Tj 0 -18 TD" for line in lines]
    stream_lines.extend(body)
    stream_lines.append("ET")
    return "\n".join(stream_lines).encode("latin-1")


def _make_pdf(pages_text: list[list[str]]) -> bytes:
    objects: list[bytes] = []

    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")  # 1
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(len(pages_text)))
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(pages_text)} >>".encode())  # 2

    font_obj_num = 3 + 2 * len(pages_text)
    for i, lines in enumerate(pages_text):
        page_obj_num = 3 + 2 * i
        content_obj_num = page_obj_num + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /Resources << /Font << /F1 {font_obj_num} 0 R >> >> "
                f"/MediaBox [0 0 612 792] /Contents {content_obj_num} 0 R >>"
            ).encode()
        )
        content = _text_object(lines)
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode() + content + b"\nendstream"
        )

    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")  # font

    buf = bytearray()
    buf += b"%PDF-1.4\n"
    offsets = [0]
    for i, obj in enumerate(objects, start=1):
        offsets.append(len(buf))
        buf += f"{i} 0 obj\n".encode() + obj + b"\nendobj\n"

    xref_offset = len(buf)
    buf += f"xref\n0 {len(objects) + 1}\n".encode()
    buf += b"0000000000 65535 f \n"
    for off in offsets[1:]:
        buf += f"{off:010d} 00000 n \n".encode()
    buf += (
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref_offset}\n%%EOF"
    ).encode()
    return bytes(buf)


def main() -> None:
    pages = [
        [
            "SUPPLY AND SERVICES AGREEMENT",
            "",
            "This contract is entered into between Acme Corp and Nile Traders.",
            "Contract reference: NT-2026-014",
            "",
            "See page 2 for the approved contract value.",
        ],
        [
            "APPROVED CONTRACT VALUE",
            "",
            "The total approved contract value under this agreement is 60000.00 EGP.",
            "This value covers all deliverables listed in Schedule A.",
            "",
            "Approved by: Finance Department, Acme Corp",
        ],
    ]
    pdf_bytes = _make_pdf(pages)
    out_path = Path(__file__).resolve().parent.parent.parent / "sample_data" / "sample_contract.pdf"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(pdf_bytes)
    print(f"wrote {out_path} ({len(pdf_bytes)} bytes)")


if __name__ == "__main__":
    main()

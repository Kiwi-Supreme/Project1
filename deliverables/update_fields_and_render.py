"""
update_fields_and_render.py

Uses the installed Microsoft Word to do the two things python-docx cannot:

  1. Update every field in the document, so the Table of Contents' PAGEREF
     fields resolve to real page numbers instead of the placeholder "1"
     they carry until Word computes the layout.
  2. Export a PDF, which is then rasterised so the finished pages can
     actually be looked at rather than merely assumed correct.

Usage:  python deliverables/update_fields_and_render.py <file.docx> [out_dir]
"""

import os
import sys

import win32com.client as win32

WD_EXPORT_PDF = 17


def update_and_export(docx_path, pdf_path):
    word = win32.gencache.EnsureDispatch("Word.Application")
    word.Visible = False
    word.DisplayAlerts = False
    try:
        doc = word.Documents.Open(os.path.abspath(docx_path), ReadOnly=False)
        # Twice on purpose: the first pass settles pagination, the second
        # picks up any page number that moved because of the first.
        for _ in range(2):
            doc.Fields.Update()
            for story in doc.StoryRanges:
                story.Fields.Update()
        doc.Save()
        doc.ExportAsFixedFormat(OutputFileName=os.path.abspath(pdf_path),
                                ExportFormat=WD_EXPORT_PDF)
        pages = doc.ComputeStatistics(2)  # wdStatisticPages
        doc.Close(SaveChanges=True)
        return pages
    finally:
        word.Quit()


def rasterise(pdf_path, out_dir, dpi=110):
    """Renders every page to PNG using PyMuPDF if present, else pdf2image."""
    os.makedirs(out_dir, exist_ok=True)
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF not installed; PDF written but not rasterised.")
        return []
    written = []
    with fitz.open(pdf_path) as pdf:
        for n, page in enumerate(pdf, 1):
            pix = page.get_pixmap(dpi=dpi)
            path = os.path.join(out_dir, f"page-{n:02d}.png")
            pix.save(path)
            written.append(path)
    return written


if __name__ == "__main__":
    src = sys.argv[1] if len(sys.argv) > 1 else \
        r"C:\Users\SHIVANI\Downloads\BCSE497J_Project_I_Report_Final_v2.docx"
    out_dir = sys.argv[2] if len(sys.argv) > 2 else \
        os.path.join(os.path.dirname(os.path.abspath(src)), "_render")
    pdf = os.path.splitext(src)[0] + ".pdf"

    pages = update_and_export(src, pdf)
    print(f"fields updated, PDF exported: {pdf}  ({pages} pages)")
    for path in rasterise(pdf, out_dir):
        print("  ", path)

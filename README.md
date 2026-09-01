# Contact Card

A small tool that helps digitize handwritten and printed contact cards — upload a scan, extract the text with OCR, and review/correct the results before it gets used anywhere downstream.

## Background

This started as a proof-of-concept exploring how to reduce the manual effort of hand-entering ~100 contact cards a month, collected on paper at events. The cards are a mix of handwritten and printed text, which turns out to be a genuinely hard OCR problem — most tooling is built for clean, printed documents, not messy handwriting.

Since the source data is personal contact information, everything in this project runs **fully locally** — no cloud OCR APIs, no data leaving the machine.

## What it does

- Upload a card as a PDF or image
- Extracts text using one of two local OCR engines (switchable in the UI):
  - **Tesseract** — fast, classical OCR, but struggles badly with handwriting
  - **EasyOCR** — deep-learning based, noticeably better on messy handwriting, though still far from perfect
- Displays each detected field next to the original image, editable, with a confidence score (where available) — so a human can quickly correct the OCR's guesses rather than trusting them blindly

## Why a review step, not just "better OCR"

Handwriting recognition on real, messy, inconsistent samples is unreliable even with the better of the two engines tested here. Rather than chasing higher OCR accuracy indefinitely, this project treats a human-in-the-loop review as a first-class part of the design — the OCR gives a starting draft, a person confirms or fixes it.

## Tech stack

- [uv](https://docs.astral.sh/uv/) — dependency and environment management
- [ruff](https://docs.astral.sh/ruff/) — linting and formatting
- [Streamlit](https://streamlit.io/) — the review UI
- [FastAPI](https://fastapi.tiangolo.com/) — API scaffolding (in progress)
- [Tesseract](https://github.com/tesseract-ocr/tesseract) / [EasyOCR](https://github.com/JaidedAI/EasyOCR) — OCR engines

## Getting started

**Requirements:** [uv](https://docs.astral.sh/uv/getting-started/installation/) installed, and [Tesseract](https://tesseract-ocr.github.io/tessdoc/Installation.html) available on your system (e.g. `brew install tesseract` on macOS) since `pytesseract` calls it as an external binary.

```bash
git clone <this-repo-url>
cd contact-card
uv sync
uv run contact-card
```

This launches the Streamlit review app in your browser. Upload a card, pick an OCR engine, and see the extracted fields.

## Known limitations

- OCR accuracy on handwriting is inconsistent, especially with Tesseract — this is expected and part of why the review step exists
- Only the first page of a multi-page PDF is currently processed
- The fundraisingbox API integration (the original "make this actually save the contact somewhere" step) is not yet included in this version

## Possible next steps

- Map extracted text chunks to actual named fields (name, email, phone, address) instead of a flat list
- Try additional local OCR engines (e.g. PaddleOCR) for comparison
- Image preprocessing (deskew, contrast) to improve OCR input quality
- Wire up the FastAPI layer to submit confirmed data to a real backend

## License

MIT

![Contact Card review UI](assets/Streamlit_UI.png)

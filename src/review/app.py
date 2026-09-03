# src/review/app.py

import logging
import os
import tempfile

import streamlit as st
from pdf2image import convert_from_path
from PIL import Image

from ingestion.ingestion import extract_fields

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)

st.set_page_config(page_title="Contact Card Review", layout="wide")
st.title("Contact Card Review")

st.markdown(
    """
    <style>
    html, body, [class*="css"] {
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

uploaded_file = st.file_uploader(
    "Upload a contact card (PDF or image)", type=["pdf", "png", "jpg", "jpeg"]
)

engine = st.radio(
    "OCR engine/SVLM",
    options=["tesseract", "easyocr", "local_vlm"],
    horizontal=True,
    help=(
        "Tesseract: fast, classical OCR, weak on handwriting. "
        "EasyOCR: local deep-learning OCR, decent on handwriting. "
        "Qwen VL: local vision LLM via LM Studio — requires LM Studio "
        "running with a Qwen3-VL model loaded."
    ),
)

if uploaded_file is not None:
    suffix = os.path.splitext(uploaded_file.name)[1]
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(uploaded_file.getvalue())
        tmp_path = tmp.name

    if suffix.lower() == ".pdf":
        pages = convert_from_path(tmp_path)
        if len(pages) > 1:
            st.warning(
                f"This PDF has {len(pages)} pages — only the first page is processed."
            )
        image = pages[0]
    else:
        image = Image.open(tmp_path)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Card image")
        st.image(image, width="stretch")

    with col2:
        st.subheader("Extracted fields (edit as needed)")

        try:
            with st.spinner(f"Running {engine}..."):
                results = extract_fields(image, engine=engine)
        except RuntimeError as e:
            st.error(str(e))
            results = []

        for i, field in enumerate(results):
            confidence = field.confidence
            label = (
                f"Field {i + 1} (confidence: {confidence:.2f})"
                if confidence is not None
                else f"Field {i + 1}"
            )
            st.text_input(label, value=field.text, key=f"field_{i}_{engine}")

    os.unlink(tmp_path)
else:
    st.info("Upload a card above to get started.")

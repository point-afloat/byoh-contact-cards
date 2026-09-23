# src/review/app.py

import logging
import os
import tempfile

import streamlit as st
from pdf2image import convert_from_path
from PIL import Image

from ingestion.ingestion import Contact, extract_fields

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

engine = "local_vlm"

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

        contact: Contact | None
        try:
            with st.spinner(f"Running {engine}..."):
                contact = extract_fields(image, engine=engine)
        except RuntimeError as e:
            st.error(str(e))
            contact = None

        if contact is not None:
            for field_name in type(contact).model_fields:
                label = field_name.replace("_", " ").title()
                value = getattr(contact, field_name) or ""
                st.text_input(label, value=value, key=f"{field_name}_{engine}")

    os.unlink(tmp_path)
else:
    st.info("Upload a card above to get started.")

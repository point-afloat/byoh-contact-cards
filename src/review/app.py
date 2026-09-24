# src/review/app.py

import logging
import os
import tempfile
from dataclasses import asdict

import streamlit as st
from pdf2image import convert_from_path
from PIL import Image

from fundraisingbox.request import (
    CONTACTPILOT_CUSTOM_FIELD_ID,
    CONTACTPILOT_CUSTOM_FIELD_NAME,
    fundraisingbox_request,
    search_companies,
)
from fundraisingbox.request_model import Anrede, CustomField, FundraisingBoxRequest
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

if "upload_version" not in st.session_state:
    st.session_state.upload_version = 0

# Widget keys carry the upload version so a reset (bumping the version) gives
# every field a fresh key — otherwise Streamlit keeps showing the previous
# card's edited values even after the uploader itself is cleared.
key_suffix = f"local_vlm_{st.session_state.upload_version}"

uploaded_file = st.file_uploader(
    "Upload a contact card (PDF or image)",
    type=["pdf", "png", "jpg", "jpeg"],
    key=f"uploader_{st.session_state.upload_version}",
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

        # The image is fully read into memory by extract_fields above, so
        # the temp file can be cleaned up now regardless of what happens
        # below (including a rerun triggered by a successful submission).
        os.unlink(tmp_path)

        if contact is not None:
            selected_company_id: int | None = None

            for field_name in type(contact).model_fields:
                label = field_name.replace("_", " ").title()
                value = getattr(contact, field_name) or ""
                st.text_input(label, value=value, key=f"{field_name}_{key_suffix}")

                if field_name == "company":
                    # FundraisingBox models donors as companies (existing
                    # records have no first/last name at all), so linking to
                    # an existing company via company_id — rather than
                    # sending a free-text company_name alongside a person's
                    # identity fields — is what avoids the "not_editable"
                    # error on first_name/last_name/salutation. Re-search
                    # only when the company text actually changes, not on
                    # every rerun. Rendered right under the Company field
                    # itself since it's directly acting on that value.
                    company_value = st.session_state.get(f"company_{key_suffix}", "")
                    matches_key = f"company_matches_{key_suffix}"
                    searched_for_key = f"company_matches_query_{key_suffix}"

                    if (
                        company_value
                        and st.session_state.get(searched_for_key) != company_value
                    ):
                        try:
                            with st.spinner(
                                f"Searching FundraisingBox for '{company_value}'..."
                            ):
                                st.session_state[matches_key] = search_companies(
                                    company_value
                                )
                        except RuntimeError as e:
                            st.error(f"FundraisingBox company search failed: {e}")
                            st.session_state[matches_key] = []
                        st.session_state[searched_for_key] = company_value

                    matches = st.session_state.get(matches_key) or []
                    match_options: list[tuple[str, int | None]] = [
                        ("Don't link — keep company name as a note only", None)
                    ]
                    for m in matches:
                        addresses = m.get("fb_person_addresses") or []
                        city = addresses[0].get("city") if addresses else None
                        match_label = m["company_name"] + (f" — {city}" if city else "")
                        match_options.append((match_label, m["id"]))

                    if company_value:
                        if matches:
                            plural = "y" if len(matches) == 1 else "ies"
                            st.caption(
                                f"Found {len(matches)} matching compan{plural} "
                                "in FundraisingBox."
                            )
                        else:
                            st.caption("No matching company found in FundraisingBox.")

                    selected_match = st.selectbox(
                        "↳ Link to existing FundraisingBox company",
                        options=match_options,
                        format_func=lambda o: o[0],
                        key=f"company_match_{key_suffix}",
                    )
                    assert selected_match is not None  # non-empty options
                    selected_company_id = selected_match[1]

            salutation = st.selectbox(
                "Salutation",
                options=list(Anrede),
                format_func=lambda a: a.value,
                key=f"salutation_{key_suffix}",
            )
            assert salutation is not None  # non-empty options, always selected

            if st.button("Send to FundraisingBox"):
                first_name = st.session_state.get(f"first_name_{key_suffix}", "")
                last_name = st.session_state.get(f"last_name_{key_suffix}", "")

                if not first_name or not last_name:
                    st.warning("First name and last name are required before sending.")
                else:
                    company = st.session_state.get(f"company_{key_suffix}", "")
                    phone = st.session_state.get(f"phone_{key_suffix}", "")
                    email = st.session_state.get(f"email_{key_suffix}", "")
                    street = st.session_state.get(f"street_{key_suffix}", "")
                    city = st.session_state.get(f"city_{key_suffix}", "")

                    # Only note the company as free text when it wasn't
                    # linked via company_id above — sending company_name
                    # alongside person identity fields is what triggers
                    # FundraisingBox's "not_editable" error on those fields.
                    info_lines = []
                    if company and selected_company_id is None:
                        info_lines.append(f"Company: {company}")
                    if phone:
                        info_lines.append(f"Phone: {phone}")
                    if email:
                        info_lines.append(f"Email: {email}")
                    if street or city:
                        info_lines.append(
                            f"Address: {', '.join(filter(None, [street, city]))}"
                        )

                    fb_request = FundraisingBoxRequest(
                        first_name=first_name,
                        last_name=last_name,
                        salutation=salutation,
                        company_id=selected_company_id,
                        position=st.session_state.get(f"job_title_{key_suffix}")
                        or None,
                        info="\n".join(info_lines) or None,
                        fb_custom_fields=[
                            CustomField(
                                id=CONTACTPILOT_CUSTOM_FIELD_ID,
                                name=CONTACTPILOT_CUSTOM_FIELD_NAME,
                                value="Sync",
                            )
                        ],
                    )

                    try:
                        with st.spinner("Sending to FundraisingBox..."):
                            fundraisingbox_request(asdict(fb_request))
                    except RuntimeError as e:
                        st.error(str(e))
                    else:
                        st.toast("Contact sent to FundraisingBox.", icon="✅")
                        st.session_state.upload_version += 1
                        st.rerun()
else:
    st.info("Upload a card above to get started.")

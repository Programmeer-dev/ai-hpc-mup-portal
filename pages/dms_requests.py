from datetime import datetime
from pathlib import Path
from typing import Optional

import streamlit as st

from dms_core import DmsManager, RequestStatus, RequestType
from dms_core.models import DocumentTemplate, SessionLocal
from municipality_utils import get_all_municipalities, validate_municipality


DOCUMENTS_DIR = Path("documents")
DOCUMENTS_DIR.mkdir(exist_ok=True)


SEMI_DIGITAL_TYPES = {
    RequestType.LICNA_KARTA,
    RequestType.PASOS,
    RequestType.VOZACKA_DOZVOLA,
}


def _service_catalog() -> dict:
    return {
        "MUP (polu-digitalno)": [
            {
                "label": "Lična karta",
                "type": RequestType.LICNA_KARTA,
                "note": "Biometrija i preuzimanje dokumenta se obavljaju fizički.",
            },
            {
                "label": "Pasoš",
                "type": RequestType.PASOS,
                "note": "Biometrija i preuzimanje dokumenta se obavljaju fizički.",
            },
            {
                "label": "Vozačka dozvola",
                "type": RequestType.VOZACKA_DOZVOLA,
                "note": "Preuzimanje dozvole je fizičko u MUP centru.",
            },
        ],
        "Turizam (potpuno digitalno)": [
            {
                "label": "Registracija nekretnine",
                "type": RequestType.TURIZAM_REGISTRACIJA,
                "note": "Kompletan proces je digitalan bez obaveznog dolaska.",
            },
            {
                "label": "Turistička licenca",
                "type": RequestType.TURIZAM_LICENCA,
                "note": "Kompletan proces je digitalan bez obaveznog dolaska.",
            },
            {
                "label": "Dozvola za adaptaciju",
                "type": RequestType.TURIZAM_DOZVOLA_GRADNJE,
                "note": "Kompletan proces je digitalan bez obaveznog dolaska.",
            },
        ],
    }


def _format_status(status: RequestStatus) -> str:
    labels = {
        RequestStatus.DRAFT: "Nacrt",
        RequestStatus.SUBMITTED: "Podnesen",
        RequestStatus.UNDER_REVIEW: "U obradi",
        RequestStatus.PENDING_USER: "Čeka korisnika",
        RequestStatus.APPROVED: "Odobren",
        RequestStatus.REJECTED: "Odbijen",
        RequestStatus.COMPLETED: "Završen",
    }
    return labels.get(status, status.value)


def _render_template_info(db, request_type: RequestType) -> Optional[DocumentTemplate]:
    template = db.query(DocumentTemplate).filter_by(request_type=request_type.value).first()
    if not template:
        st.warning("Nisu pronađeni šabloni dokumenata za ovu uslugu.")
        return None

    c1, c2, c3 = st.columns(3)
    with c1:
        st.metric("Procijenjeni rok", f"{template.estimated_days} dana")
    with c2:
        fee_text = f"{template.processing_fee_eur:.2f} EUR" if template.processing_fee_eur else "Bez takse"
        st.metric("Taksa", fee_text)
    with c3:
        st.metric("Broj dokumenata", len(template.required_documents or []))

    st.markdown("#### Potrebna dokumenta")
    for idx, doc in enumerate(template.required_documents or [], start=1):
        doc_name = doc.get("naziv", f"Dokument {idx}") if isinstance(doc, dict) else str(doc)
        doc_desc = doc.get("opis", "") if isinstance(doc, dict) else ""
        st.markdown(f"{idx}. {doc_name}")
        if doc_desc:
            st.caption(doc_desc)

    if template.instructions:
        st.info(template.instructions)

    return template


def dms_request_page() -> None:
    st.title("Podnesi zahtjev")
    st.caption("Jedinstven portal za MUP i turističke usluge")

    if not st.session_state.get("user"):
        st.warning("Morate biti prijavljeni.")
        return

    db = SessionLocal()
    dms = DmsManager(db)

    try:
        catalog = _service_catalog()
        group = st.radio("Tip usluge", list(catalog.keys()), horizontal=True)
        selected = st.selectbox(
            "Odaberite uslugu",
            options=catalog[group],
            format_func=lambda item: item["label"],
        )

        request_type = selected["type"]
        is_semi_digital = request_type in SEMI_DIGITAL_TYPES

        if is_semi_digital:
            st.warning(selected["note"])
        else:
            st.success(selected["note"])

        template = _render_template_info(db, request_type)

        with st.form("submit_request_form"):
            st.markdown("### Podaci zahtjeva")
            reason = st.text_input("Razlog zahtjeva")
            description = st.text_area("Dodatni opis", height=120)

            details = {
                "service_group": "semi_digital" if is_semi_digital else "full_digital",
                "physical_presence_required": is_semi_digital,
                "requested_at": datetime.now().isoformat(),
            }

            if not is_semi_digital:
                st.markdown("### Podaci o nekretnini")
                property_name = st.text_input("Naziv objekta")
                property_address = st.text_input("Adresa objekta")
                property_city = st.selectbox("Opština objekta", get_all_municipalities())
                capacity = st.number_input("Kapacitet (broj osoba)", min_value=1, max_value=200, value=2)
                rooms = st.number_input("Broj soba", min_value=1, max_value=50, value=1)

                details.update(
                    {
                        "property_name": property_name,
                        "property_address": property_address,
                        "property_city": property_city,
                        "capacity": int(capacity),
                        "rooms": int(rooms),
                    }
                )

            uploaded_files = st.file_uploader(
                "Dodajte dokumenta",
                accept_multiple_files=True,
                type=["pdf", "jpg", "jpeg", "png"],
            )

            confirm = st.checkbox("Potvrđujem da su podaci tačni.")
            submit = st.form_submit_button("Podnesi zahtjev", type="primary")

            if submit:
                if not confirm:
                    st.error("Morate potvrditi tačnost podataka.")
                elif not st.session_state.get("user_city"):
                    st.error("Korisnik nema postavljenu opštinu prebivališta.")
                elif not is_semi_digital and not validate_municipality(details.get("property_city", "")):
                    st.error("Opština objekta nije validna.")
                else:
                    request = dms.create_request(
                        request_type=request_type,
                        user_id=st.session_state.user,
                        user_email=st.session_state.get("user_email") or "",
                        user_city=st.session_state.user_city,
                        details=details,
                        description=description,
                        reason=reason,
                    )
                    dms.submit_request(request.id, changed_by=st.session_state.user)

                    request_dir = DOCUMENTS_DIR / str(request.id)
                    request_dir.mkdir(exist_ok=True)

                    for file in uploaded_files or []:
                        file_path = request_dir / file.name
                        with open(file_path, "wb") as out:
                            out.write(file.getbuffer())
                        dms.upload_document(request.id, doc_name=file.name, file_path=str(file_path))

                    if not is_semi_digital and details.get("property_address"):
                        dms.register_tourism_property(
                            request_id=request.id,
                            owner_id=st.session_state.user,
                            property_type="turizam_objekat",
                            address=details["property_address"],
                            city=details["property_city"],
                            capacity=details["capacity"],
                            rooms=details["rooms"],
                            amenities=[],
                        )

                    dms.add_comment(
                        request_id=request.id,
                        author=st.session_state.user,
                        content="Zahtjev je podnesen preko građanskog portala.",
                        author_type="user",
                    )

                    st.success(f"Zahtjev #{request.id} je uspješno podnesen.")
                    st.info("Status i komunikaciju pratite u sekciji 'Moji zahtjevi'.")

    finally:
        db.close()


def my_requests_page() -> None:
    st.title("Moji zahtjevi")

    if not st.session_state.get("user"):
        st.warning("Morate biti prijavljeni.")
        return

    db = SessionLocal()
    dms = DmsManager(db)

    try:
        requests = dms.get_user_requests(st.session_state.user)
        if not requests:
            st.info("Nemate podnesenih zahtjeva.")
            return

        selected_status = st.selectbox(
            "Filter po statusu",
            ["Svi"] + [status.value for status in RequestStatus],
            format_func=lambda value: "Svi" if value == "Svi" else _format_status(RequestStatus(value)),
        )

        if selected_status != "Svi":
            requests = [req for req in requests if req.status.value == selected_status]

        for request in requests:
            mode = request.details.get("service_group") if request.details else "semi_digital"
            mode_label = "Polu-digitalno" if mode == "semi_digital" else "Potpuno digitalno"

            with st.container(border=True):
                c1, c2, c3 = st.columns([3, 2, 2])
                with c1:
                    st.markdown(f"### #{request.id} - {request.request_type.value.replace('_', ' ').title()}")
                    st.caption(f"Podnesen: {request.created_at.strftime('%d.%m.%Y %H:%M')}")
                with c2:
                    st.write(f"Status: {_format_status(request.status)}")
                with c3:
                    st.write(f"Tip toka: {mode_label}")

                if request.details and request.details.get("physical_presence_required"):
                    st.warning("Za ovu uslugu je potreban fizički dolazak u završnoj fazi.")
                else:
                    st.success("Za ovu uslugu proces se vodi digitalno do kraja.")

                with st.expander("Detalji zahtjeva"):
                    st.write(f"Razlog: {request.reason or '-'}")
                    st.write(f"Opis: {request.description or '-'}")

                    st.markdown("#### Dokumenta")
                    if request.documents_metadata:
                        for doc in request.documents_metadata:
                            uploaded_at = doc.get("uploaded_at", "")[:16].replace("T", " ")
                            st.write(f"- {doc.get('name')} ({doc.get('status', 'pending')}) {uploaded_at}")
                    else:
                        st.caption("Nema uploadovanih dokumenata.")

                    st.markdown("#### Komentari")
                    for comment in dms.get_visible_comments(request.id, for_user=True):
                        created = comment.created_at.strftime("%d.%m.%Y %H:%M") if comment.created_at else ""
                        st.write(f"{comment.author} ({created}): {comment.content}")

                    if request.status not in [RequestStatus.COMPLETED, RequestStatus.REJECTED]:
                        reply = st.text_area("Dodajte komentar", key=f"comment_{request.id}")
                        if st.button("Pošalji komentar", key=f"send_{request.id}"):
                            if reply.strip():
                                dms.add_comment(
                                    request.id,
                                    author=st.session_state.user,
                                    content=reply.strip(),
                                    author_type="user",
                                )
                                st.success("Komentar je sačuvan.")
                                st.rerun()

                    st.markdown("#### Audit trail")
                    if request.status_history:
                        for entry in sorted(request.status_history, key=lambda item: item.changed_at):
                            changed = entry.changed_at.strftime("%d.%m.%Y %H:%M") if entry.changed_at else ""
                            st.write(
                                f"- {changed}: {entry.from_status.value} -> {entry.to_status.value} ({entry.changed_by or 'sistem'})"
                            )
                    else:
                        st.caption("Nema zabilježenih promjena statusa.")

    finally:
        db.close()

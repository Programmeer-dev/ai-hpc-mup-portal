from datetime import datetime

import streamlit as st

from dms_core import DmsManager, RequestStatus
from dms_core.models import DmsRequest, SessionLocal


def _status_label(status: RequestStatus) -> str:
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


def admin_dashboard() -> None:
    st.title("Admin/Officer panel")

    if not st.session_state.get("is_admin"):
        st.error("Nemate pristup ovoj sekciji.")
        return

    db = SessionLocal()
    dms = DmsManager(db)

    try:
        tab_dashboard, tab_queue, tab_archive = st.tabs(["Dashboard", "Aktivni zahtjevi", "Arhiva"])

        with tab_dashboard:
            stats = dms.get_statistics()
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Ukupno", stats["total_requests"])
            c2.metric("Podneseni", stats["by_status"].get("submitted", 0))
            c3.metric("U obradi", stats["by_status"].get("under_review", 0))
            c4.metric("Prekoračen rok", stats.get("overdue_count", 0))

            st.markdown("### Kritični slučajevi")
            overdue = dms.get_overdue_requests()
            if overdue:
                for req in overdue:
                    late_days = (datetime.now() - req.estimated_completion).days
                    st.warning(
                        f"Zahtjev #{req.id} ({req.request_type.value}) kasni {late_days} dana."
                    )
            else:
                st.success("Nema prekoračenih rokova.")

        with tab_queue:
            active = dms.get_active_requests()
            if not active:
                st.info("Nema aktivnih zahtjeva.")
            else:
                chosen = st.selectbox(
                    "Odaberite zahtjev",
                    options=active,
                    format_func=lambda req: f"#{req.id} | {req.request_type.value} | {req.user_id} | {req.status.value}",
                )
                _render_request_detail(chosen, dms)

        with tab_archive:
            completed = db.query(DmsRequest).filter(
                DmsRequest.status.in_([RequestStatus.COMPLETED, RequestStatus.REJECTED])
            ).order_by(DmsRequest.updated_at.desc()).limit(50).all()

            if not completed:
                st.caption("Arhiva je prazna.")
            else:
                for req in completed:
                    st.write(
                        f"#{req.id} | {req.request_type.value} | {_status_label(req.status)} | "
                        f"{req.updated_at.strftime('%d.%m.%Y %H:%M')}"
                    )

    finally:
        db.close()


def _render_request_detail(request, dms: DmsManager) -> None:
    st.markdown(f"### Zahtjev #{request.id}")

    c1, c2, c3 = st.columns(3)
    c1.write(f"Korisnik: {request.user_id}")
    c1.write(f"Email: {request.user_email}")
    c2.write(f"Status: {_status_label(request.status)}")
    c2.write(f"Prioritet: {request.priority.value}")
    c3.write(f"Opština: {request.user_city}")
    c3.write(f"Rok: {request.estimated_completion.strftime('%d.%m.%Y') if request.estimated_completion else '-'}")

    st.markdown("#### Opis i detalji")
    st.write(request.description or "-")
    if request.details:
        st.json(request.details)

    st.markdown("#### Dokumenta")
    if request.documents_metadata:
        for doc in request.documents_metadata:
            st.write(f"- {doc.get('name')} ({doc.get('status', 'pending_review')})")
    else:
        st.caption("Nema uploadovanih dokumenata.")

    st.markdown("#### Komunikacija")
    comments = dms.get_visible_comments(request.id, for_user=False)
    if comments:
        for comment in comments:
            created = comment.created_at.strftime("%d.%m.%Y %H:%M") if comment.created_at else ""
            visibility = "interno" if comment.is_internal else "vidljivo korisniku"
            st.write(f"{comment.author} ({created}, {visibility}): {comment.content}")
    else:
        st.caption("Nema komentara.")

    officer_comment = st.text_area("Komentar službenika", key=f"officer_comment_{request.id}")
    internal_only = st.checkbox("Interni komentar", key=f"internal_comment_{request.id}")
    if st.button("Sačuvaj komentar", key=f"save_comment_{request.id}"):
        if officer_comment.strip():
            dms.add_comment(
                request.id,
                author=st.session_state.user,
                content=officer_comment.strip(),
                author_type="admin",
                is_internal=internal_only,
            )
            st.success("Komentar je sačuvan.")
            st.rerun()

    st.markdown("#### Promjena statusa")
    available = dms.get_available_transitions(request.id)
    if not available:
        st.caption("Za trenutni status nema dostupnih tranzicija.")
        return

    new_status = st.selectbox(
        "Novi status",
        options=available,
        format_func=_status_label,
        key=f"status_change_{request.id}",
    )
    reason = st.text_area("Napomena za promjenu", key=f"status_reason_{request.id}")

    if st.button("Potvrdi promjenu", key=f"status_submit_{request.id}", type="primary"):
        try:
            if new_status == RequestStatus.UNDER_REVIEW and not request.assigned_to:
                request.assigned_to = st.session_state.user

            if new_status == RequestStatus.PENDING_USER and not reason.strip():
                st.error("Unesite poruku za korisnika kada status prelazi na 'Čeka korisnika'.")
                return

            dms.transition_request(
                request.id,
                new_status,
                changed_by=st.session_state.user,
                reason=reason.strip() or None,
            )

            if new_status == RequestStatus.PENDING_USER and reason.strip():
                dms.add_comment(
                    request.id,
                    author=st.session_state.user,
                    content=reason.strip(),
                    author_type="admin",
                    is_internal=False,
                )

            if new_status == RequestStatus.REJECTED and reason.strip():
                request.rejection_reason = reason.strip()
                dms.db.commit()

            st.success("Status je ažuriran.")
            st.rerun()
        except ValueError as exc:
            st.error(str(exc))

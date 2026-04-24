from datetime import datetime
import csv
import io
import json
import logging

import pandas as pd
import streamlit as st

from dms_core import DmsManager, RequestStatus
from dms_core.models import DmsRequest, SessionLocal


logger = logging.getLogger("dms_portal.admin")


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


def _build_audit_csv(audit_payload: dict) -> str:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["section", "timestamp", "actor", "action", "details"])

    req = audit_payload.get("request", {})
    writer.writerow(
        [
            "request",
            req.get("created_at") or "",
            req.get("user_id") or "",
            f"{req.get('request_type', '')}:{req.get('status', '')}",
            req.get("reason") or "",
        ]
    )

    for row in audit_payload.get("status_history", []):
        writer.writerow(
            [
                "status_history",
                row.get("changed_at") or "",
                row.get("changed_by") or "",
                f"{row.get('from_status', '')}->{row.get('to_status', '')}",
                row.get("reason") or "",
            ]
        )

    for row in audit_payload.get("comments", []):
        writer.writerow(
            [
                "comment",
                row.get("created_at") or "",
                row.get("author") or "",
                row.get("author_type") or "",
                row.get("content") or "",
            ]
        )

    return output.getvalue()


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
            st.markdown("### KPI pregled")
            if st.button("Primijeni SLA eskalaciju", key="sla_escalation_btn"):
                result = dms.apply_sla_escalation()
                if result["escalated"]:
                    st.warning(f"Eskalirano predmeta: {result['escalated']}")
                else:
                    st.info("Nema novih SLA eskalacija.")

            kpis = dms.get_kpi_metrics()
            kc1, kc2, kc3, kc4 = st.columns(4)
            kc1.metric("Ukupno zahtjeva", kpis["total_requests"])
            kc2.metric("Prosjek prve obrade (h)", kpis["avg_first_review_hours"])
            kc3.metric("Stopa zavrsetka", f"{kpis['completion_rate_percent']}%")
            kc4.metric("Stopa vracanja", f"{kpis['correction_rate_percent']}%")

            st.markdown("### KPI trendovi (nedeljno)")
            trends = dms.get_weekly_trends(weeks=8)
            trends_df = pd.DataFrame(trends)
            if not trends_df.empty:
                st.dataframe(trends_df, use_container_width=True)
                chart_df = trends_df.set_index("week")[["created", "submitted", "completed"]]
                st.line_chart(chart_df)

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

    st.markdown("#### Audit export")
    audit_payload = dms.build_audit_pack(request.id)
    st.download_button(
        "Preuzmi audit JSON",
        data=json.dumps(audit_payload, ensure_ascii=False, indent=2),
        file_name=f"audit_request_{request.id}.json",
        mime="application/json",
        key=f"audit_export_{request.id}",
    )
    st.download_button(
        "Preuzmi audit CSV",
        data=_build_audit_csv(audit_payload),
        file_name=f"audit_request_{request.id}.csv",
        mime="text/csv",
        key=f"audit_export_csv_{request.id}",
    )

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
                actor_role="admin",
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
        except PermissionError as exc:
            st.error(str(exc))
        except Exception:
            logger.exception("Unexpected admin status update failure request_id=%s", request.id)
            st.error("Doslo je do greske pri promjeni statusa. Pokusajte ponovo.")

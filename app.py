import json
import os
from pathlib import Path
from typing import Set

import streamlit as st
from dotenv import load_dotenv

from database.database import (
    authenticate_user,
    create_user,
    get_user_city,
    get_user_email,
    is_user_admin,
    init_db,
    set_user_city,
)
from dms_core.init_dms import init_dms_database, init_dms_templates
from dms_core.models import DocumentTemplate, SessionLocal
from municipality_utils import get_all_municipalities, validate_municipality
from pages.admin_panel import admin_dashboard
from pages.dms_requests import dms_request_page, my_requests_page


BASE_DIR = Path(__file__).resolve().parent
SESSION_FILE = BASE_DIR / "data" / "session.json"
DEFAULT_ADMIN_USERS = "admin,rapoz"


load_dotenv()


st.set_page_config(
    page_title="DMS MUP Portal",
    page_icon="📋",
    layout="wide",
)


def init_session_state() -> None:
    defaults = {
        "user": None,
        "user_city": None,
        "user_email": None,
        "is_admin": False,
        "current_view": "dashboard",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def get_admin_users() -> Set[str]:
    raw = os.getenv("APP_ADMIN_USERS", DEFAULT_ADMIN_USERS)
    return {item.strip() for item in raw.split(",") if item.strip()}


def is_admin_user(username: str) -> bool:
    return is_user_admin(username) or username in get_admin_users()


def restore_session() -> None:
    if st.session_state.user or not SESSION_FILE.exists():
        return
    try:
        with open(SESSION_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        username = data.get("user")
        if username:
            st.session_state.user = username
            st.session_state.user_city = get_user_city(username)
            st.session_state.user_email = get_user_email(username)
            st.session_state.is_admin = is_admin_user(username)
    except Exception:
        # Ignore stale or invalid session file to keep startup robust.
        pass


def persist_session(username: str) -> None:
    SESSION_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SESSION_FILE, "w", encoding="utf-8") as file:
        json.dump({"user": username}, file)


def clear_session() -> None:
    if SESSION_FILE.exists():
        SESSION_FILE.unlink()
    st.session_state.user = None
    st.session_state.user_city = None
    st.session_state.user_email = None
    st.session_state.is_admin = False
    st.session_state.current_view = "dashboard"


def bootstrap_data() -> None:
    init_db()

    db = SessionLocal()
    try:
        init_dms_database(db)
        has_templates = db.query(DocumentTemplate).count() > 0
        if not has_templates:
            init_dms_templates(
                db,
                mup_rules_path=str(BASE_DIR / "database" / "mup_rules.json"),
                turizam_path=str(BASE_DIR / "requirements_data" / "turizam_requirements.json"),
            )
    finally:
        db.close()


def render_auth_page() -> None:
    st.title("Digitalizacija MUP usluga")
    st.caption("Diplomski MVP: DMS za polu-digitalne i potpuno digitalne administrativne servise")

    login_tab, register_tab = st.tabs(["Prijava", "Registracija"])

    with login_tab:
        with st.form("login_form"):
            username = st.text_input("Korisnicko ime")
            password = st.text_input("Lozinka", type="password")
            remember = st.checkbox("Zapamti prijavu")
            submit = st.form_submit_button("Prijavi se", use_container_width=True)

            if submit:
                if not username or not password:
                    st.warning("Unesite korisnicko ime i lozinku.")
                elif not authenticate_user(username, password):
                    st.error("Pogresni kredencijali.")
                else:
                    st.session_state.user = username
                    st.session_state.user_city = get_user_city(username)
                    st.session_state.user_email = get_user_email(username)
                    st.session_state.is_admin = is_admin_user(username)
                    if remember:
                        persist_session(username)
                    st.success("Uspjesna prijava.")
                    st.rerun()

    with register_tab:
        with st.form("register_form"):
            username = st.text_input("Novo korisnicko ime")
            email = st.text_input("Email")
            municipality = st.selectbox("Opstina", get_all_municipalities())
            password = st.text_input("Lozinka", type="password")
            password_repeat = st.text_input("Potvrda lozinke", type="password")
            submit = st.form_submit_button("Registruj nalog", use_container_width=True)

            if submit:
                if not username or not email or not password:
                    st.warning("Popunite sva obavezna polja.")
                elif password != password_repeat:
                    st.error("Lozinke se ne poklapaju.")
                elif len(password) < 6:
                    st.error("Lozinka mora imati najmanje 6 karaktera.")
                elif not validate_municipality(municipality):
                    st.error("Izabrana opstina nije validna.")
                elif not create_user(username, password, email):
                    st.error("Korisnicko ime vec postoji.")
                else:
                    set_user_city(username, municipality)
                    st.success("Nalog je kreiran. Mozete se prijaviti.")


def render_dashboard() -> None:
    st.title("Korisnicki portal")
    st.markdown("### Pregled digitalnih servisa")

    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Polu-digitalne MUP usluge")
        st.write("- Licna karta")
        st.write("- Pasos")
        st.write("- Vozacka dozvola")
        st.info(
            "Online: dokumenta, prijava zahtjeva i pracenje statusa. "
            "Fizicki dolazak ostaje potreban za biometriju ili preuzimanje."
        )

    with col2:
        st.subheader("Potpuno digitalne turisticke usluge")
        st.write("- Registracija apartmana/nekretnine")
        st.write("- Turisticka licenca")
        st.write("- Dozvola za adaptaciju")
        st.success(
            "Kompletan tok je online: podnosenje, validacija, komunikacija i odluka bez dolaska."
        )


def render_help_assistant() -> None:
    from dms_core.dms_ai import get_dms_aware_response

    st.title("Pomoc i FAQ")
    st.caption("Jednostavan asistent nad DMS pravilima")

    question = st.text_input(
        "Postavite pitanje",
        placeholder="Npr. Koja dokumenta trebam za registraciju apartmana?",
    )

    if st.button("Dobij odgovor", type="primary") and question.strip():
        db = SessionLocal()
        try:
            answer = get_dms_aware_response(question.strip(), db)
            st.markdown(answer)
        finally:
            db.close()


def render_sidebar() -> None:
    with st.sidebar:
        st.markdown("## DMS Navigacija")
        st.caption(f"Korisnik: {st.session_state.user}")
        if st.session_state.user_city:
            st.caption(f"Opstina: {st.session_state.user_city}")

        options = [
            ("dashboard", "Dashboard"),
            ("submit", "Podnesi zahtjev"),
            ("requests", "Moji zahtjevi"),
            ("faq", "Pomoc/FAQ"),
        ]
        if st.session_state.is_admin:
            options.append(("admin", "Admin/Officer panel"))

        labels = {value: label for value, label in options}
        reverse = {label: value for value, label in options}

        selected_label = st.radio(
            "Sekcije",
            options=[label for _, label in options],
            index=[value for value, _ in options].index(st.session_state.current_view)
            if st.session_state.current_view in labels
            else 0,
        )
        st.session_state.current_view = reverse[selected_label]

        if st.button("Odjava", use_container_width=True):
            clear_session()
            st.rerun()


def render_main_router() -> None:
    view = st.session_state.current_view
    if view == "dashboard":
        render_dashboard()
    elif view == "submit":
        dms_request_page()
    elif view == "requests":
        my_requests_page()
    elif view == "faq":
        render_help_assistant()
    elif view == "admin":
        admin_dashboard()


def main() -> None:
    init_session_state()
    bootstrap_data()
    restore_session()

    if not st.session_state.user:
        render_auth_page()
        return

    render_sidebar()
    render_main_router()


if __name__ == "__main__":
    main()

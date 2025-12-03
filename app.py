import streamlit as st
from utils import load_rules, load_centers, detect_service, google_maps_link, get_all_cities
from queue_sim import estimate_wait_minutes, next_best_slot
from word_generator import generate_docx_confirmation
from hpc_queue_predictor import predict_best_arrival_time
from municipality_utils import get_all_municipalities
from datetime import datetime
from database.database import init_db, create_user, authenticate_user, get_user_email, get_user_city, set_user_city, save_query, get_user_queries
from streamlit_searchbox import st_searchbox
import json, os
import folium
from streamlit_folium import st_folium
from ai_chatbot import chat_with_ai, init_openai, get_fallback_response, get_accusative_form, get_genitive_form, get_locative_form
from dotenv import load_dotenv
from PIL import Image

# Load environment variables
load_dotenv()

init_db()

# Učitaj AI avatar
try:
    ai_avatar = Image.open("static/ai_avatar.png")
except:
    ai_avatar = "🤖"  # Fallback emoji ako slika ne postoji

if "user" not in st.session_state:
    st.session_state.user = None
if "page" not in st.session_state:
    st.session_state.page = "login"
if "history" not in st.session_state:
    st.session_state.history = []
if "user_city" not in st.session_state:
    st.session_state.user_city = None
if "chat_messages" not in st.session_state:
    st.session_state.chat_messages = []
if "chat_mode" not in st.session_state:
    st.session_state.chat_mode = False
if "current_service" not in st.session_state:
    st.session_state.current_service = None
if "conversation_context" not in st.session_state:
    st.session_state.conversation_context = {}

session_file = "data/session.json"
if st.session_state.user is None and os.path.exists(session_file):
    with open(session_file) as f:
        data = json.load(f)
        if "user" in data:
            st.session_state.user = data["user"]
            # Učitaj grad iz baze
            st.session_state.user_city = get_user_city(st.session_state.user)

def generate_reply(user_msg):
    rules = load_rules()
    centers = load_centers()
    found = detect_service(user_msg, rules)
    if found is None:
        return "Nisam siguran o kojoj usluzi je riječ. Pokušaj sa: lična karta, pasoš, vozačka dozvola."
    info = rules[found]
    reply_parts = [f"**Pronađena usluga: {found.title()}**\n"]
    reply_parts.append("**📄 Potrebna dokumenta:**")
    for d in info["dokumenta"]:
        reply_parts.append(f"- {d}")
    reply_parts.append(f"\n**💶 Taksa:** {info['taksa_eur']:.2f} €")
    reply_parts.append(f"**🏦 Uplata:** {info['uplata']}")
    reply_parts.append(f"**⏱️ Rok izrade:** oko {info['rok_izrade_dana']} dana")
    reply_parts.append("\n**📍 Najbliži MUP centri:**")
    for c in centers[:3]:
        link = google_maps_link(c["lat"], c["lon"], c["naziv"])
        reply_parts.append(f"- {c['naziv']} — {c['radno_vrijeme']} [Otvori u mapama]({link})")
    arrival, service, qsize = 18, 20, 12
    est = estimate_wait_minutes(arrival, service, qsize)
    slot = next_best_slot(datetime.now(), est)
    reply_parts.append(f"\n**🧮 Procjena čekanja:** ~{est} min")
    reply_parts.append(f"**Predloženi termin dolaska:** {slot.strftime('%d.%m.%Y %H:%M')}")
    return "\n".join(reply_parts)

st.set_page_config(
    page_title="MUP Portal Crne Gore", 
    page_icon="🇲🇪",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS za visual polish
st.markdown("""
<style>
    /* Animated Background with Particles */
    @keyframes float {
        0%, 100% { 
            transform: translateY(0px) translateX(0px);
            opacity: 0.8;
        }
        25% { 
            transform: translateY(-30px) translateX(30px);
            opacity: 1;
        }
        50% { 
            transform: translateY(-50px) translateX(-20px);
            opacity: 0.6;
        }
        75% { 
            transform: translateY(-20px) translateX(40px);
            opacity: 1;
        }
    }
    
    @keyframes gradientMove {
        0% { background-position: 0% 50%; }
        50% { background-position: 100% 50%; }
        100% { background-position: 0% 50%; }
    }
    
    /* Main background gradient */
    .stApp {
        background: linear-gradient(-45deg, #e3f2fd, #f3e5f5, #fff9c4, #e1f5fe);
        background-size: 400% 400%;
        animation: gradientMove 15s ease infinite;
        position: relative;
    }
    
    /* Floating particles container */
    .stApp::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        pointer-events: none;
        z-index: -1;
        background-image: 
            radial-gradient(circle, #667eea 2px, transparent 2px),
            radial-gradient(circle, #764ba2 1px, transparent 1px),
            radial-gradient(circle, #f093fb 1.5px, transparent 1.5px),
            radial-gradient(circle, #4facfe 2px, transparent 2px),
            radial-gradient(circle, #667eea 1px, transparent 1px);
        background-size: 550px 550px, 350px 350px, 450px 450px, 600px 600px, 400px 400px;
        background-position: 0 0, 40px 60px, 130px 270px, 70px 100px, 200px 150px;
        animation: float 25s ease-in-out infinite;
        opacity: 0.3;
    }
    
    /* Smooth transitions za sve elemente */
    * {
        transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1) !important;
    }
    
    /* Content wrapper - vidljiv iznad pozadine */
    .main .block-container {
        position: relative;
        z-index: 1;
    }
    
    /* Sidebar vidljiv */
    [data-testid="stSidebar"] {
        position: relative;
        z-index: 2;
    }
    
    /* Svi glavni elementi vidljivi */
    .stApp > header,
    .stApp > div {
        position: relative;
        z-index: 1;
    }
    
    /* Login page styling sa animated background */
    .login-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(-45deg, #667eea, #764ba2, #f093fb, #4facfe);
        background-size: 400% 400%;
        animation: gradientShift 15s ease infinite, fadeInDown 0.6s ease-out;
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
        box-shadow: 0 10px 40px rgba(102, 126, 234, 0.3);
        position: relative;
        overflow: hidden;
    }
    .login-header::before {
        content: "";
        position: absolute;
        width: 200%;
        height: 200%;
        top: -50%;
        left: -50%;
        background: radial-gradient(circle, rgba(255,255,255,0.1) 1px, transparent 1px);
        background-size: 50px 50px;
        animation: float 20s linear infinite;
        opacity: 0.3;
    }
    .login-header h1 {
        margin: 0;
        font-size: 2.5rem;
        font-weight: 700;
    }
    .login-header p {
        margin: 0.5rem 0 0 0;
        opacity: 0.9;
    }
    
    /* Tabs styling - Poboljšan dizajn */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        justify-content: center;
        background: transparent;
        padding: 0;
        border-bottom: 3px solid #e5e7eb;
        margin-bottom: 2rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 1rem 3rem;
        font-size: 1.2rem;
        font-weight: 700;
        background: transparent;
        border: none;
        border-bottom: 3px solid transparent;
        color: #6b7280;
        transition: all 0.3s ease;
        position: relative;
    }
    .stTabs [data-baseweb="tab"]:hover {
        background: rgba(102, 126, 234, 0.05);
        color: #667eea;
        border-bottom-color: rgba(102, 126, 234, 0.3);
    }
    .stTabs [aria-selected="true"] {
        background: transparent !important;
        color: #667eea !important;
        border-bottom: 3px solid #667eea !important;
        font-weight: 800;
    }
    .stTabs [aria-selected="true"]::after {
        content: "";
        position: absolute;
        bottom: -3px;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, #667eea, #764ba2);
        animation: slideInRight 0.4s ease-out;
    }
    
    /* Button hover effects */
    .stButton button {
        transition: all 0.3s cubic-bezier(0.4, 0.0, 0.2, 1);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }
    .stButton button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.4);
    }
    .stButton button:active {
        transform: translateY(0);
    }
    
    /* Card animations */
    div[data-testid="stVerticalBlock"] > div {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* Container styling with glassmorphism */
    div[data-testid="stContainer"] {
        background: rgba(255, 255, 255, 0.8);
        backdrop-filter: blur(10px);
        border-radius: 16px;
        border: 1px solid rgba(255, 255, 255, 0.3);
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        transition: transform 0.3s ease, box-shadow 0.3s ease;
    }
    div[data-testid="stContainer"]:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 48px rgba(0, 0, 0, 0.15);
    }
    
    /* Loading skeleton animation */
    @keyframes shimmer {
        0% { background-position: -1000px 0; }
        100% { background-position: 1000px 0; }
    }
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 1000px 100%;
        animation: shimmer 2s infinite;
        border-radius: 8px;
    }
    
    /* Fade in animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(20px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes fadeInDown {
        from { opacity: 0; transform: translateY(-30px); }
        to { opacity: 1; transform: translateY(0); }
    }
    @keyframes slideInRight {
        from { opacity: 0; transform: translateX(30px); }
        to { opacity: 1; transform: translateX(0); }
    }
    
    /* Toast notification styling */
    .toast-notification {
        position: fixed;
        top: 80px;
        right: 20px;
        background: white;
        padding: 1rem 1.5rem;
        border-radius: 12px;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
        animation: slideInRight 0.4s ease-out;
        z-index: 9999;
        border-left: 4px solid #667eea;
        max-width: 400px;
    }
    .toast-success {
        border-left-color: #10b981;
    }
    .toast-error {
        border-left-color: #ef4444;
    }
    .toast-warning {
        border-left-color: #f59e0b;
    }
    .toast-info {
        border-left-color: #3b82f6;
    }
    
    /* Metric card styling */
    div[data-testid="stMetric"] {
        background: linear-gradient(135deg, #667eea15, #764ba215);
        padding: 1.5rem;
        border-radius: 12px;
        border: 1px solid #667eea30;
        transition: all 0.3s ease;
    }
    div[data-testid="stMetric"]:hover {
        background: linear-gradient(135deg, #667eea25, #764ba225);
        transform: scale(1.05);
        box-shadow: 0 8px 24px rgba(102, 126, 234, 0.2);
    }
    
    /* Input field focus effects */
    input:focus, textarea:focus {
        border-color: #667eea !important;
        box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1) !important;
    }
    
    /* Scrollbar styling */
    ::-webkit-scrollbar {
        width: 10px;
        height: 10px;
    }
    ::-webkit-scrollbar-track {
        background: #f1f1f1;
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(135deg, #667eea, #764ba2);
        border-radius: 10px;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(135deg, #764ba2, #667eea);
    }
    
    /* Success/Error message animations */
    .stSuccess, .stError, .stWarning, .stInfo {
        animation: fadeIn 0.5s ease-out;
    }
    
    /* Progress bar styling */
    .stProgress > div > div {
        background: linear-gradient(90deg, #667eea, #764ba2);
        border-radius: 10px;
    }
</style>
""", unsafe_allow_html=True)

# Ako korisnik nije prijavljen, prikaži login/register stranicu
if not st.session_state.user:
    st.markdown("""
    <div class="login-header">
        <h1>🇲🇪 MUP Portal Crne Gore</h1>
        <p>Digitalni asistent za administrativne usluge</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Dodaj session state za praćenje uspješne registracije
    if "registration_success" not in st.session_state:
        st.session_state.registration_success = False
    
    # Ako je registracija uspješna, prikaži Prijava tab
    if st.session_state.registration_success:
        default_tab = 0  # Prijava tab
        st.session_state.registration_success = False  # Resetuj flag
    else:
        default_tab = None  # Nema default-a
    
    tab1, tab2 = st.tabs(["Prijava", "Registracija"])
    
    with tab1:
        with st.form("login_form"):
            st.subheader("Prijava")
            username = st.text_input("Korisničko ime")
            password = st.text_input("Lozinka", type="password")
            remember_me = st.checkbox("Zapamti me")
            submit = st.form_submit_button("Prijavi se", use_container_width=True)
            
            if submit:
                if username and password:
                    if authenticate_user(username, password):
                        st.session_state.user = username
                        st.session_state.user_city = get_user_city(username)
                        if remember_me:
                            os.makedirs("data", exist_ok=True)
                            with open("data/session.json", "w") as f:
                                json.dump({"user": username}, f)
                        st.success("✅ Uspješno ste se prijavili! Dobrodošli nazad.")
                        import time
                        time.sleep(0.8)
                        st.rerun()
                    else:
                        st.error("Pogrešno korisničko ime ili lozinka")
                else:
                    st.warning("Molimo popunite sva polja")
    
    with tab2:
        with st.form("register_form"):
            st.subheader("Registracija")
            new_username = st.text_input("Korisničko ime")
            new_email = st.text_input("Email")
            
            # Manuelni izbor opštine
            municipalities = get_all_municipalities()
            new_municipality = st.selectbox("Opština prebivališta", municipalities, 
                                           help="Izaberite opštinu iz koje ste")
            
            new_password = st.text_input("Lozinka", type="password")
            new_password2 = st.text_input("Potvrdi lozinku", type="password")
            
            submit_reg = st.form_submit_button("Registruj se", use_container_width=True)
            
            if submit_reg:
                if new_password != new_password2:
                    st.error("Lozinke se ne poklapaju")
                elif len(new_password) < 6:
                    st.error("Lozinka mora imati najmanje 6 karaktera")
                elif not new_username or not new_email:
                    st.error("Molimo popunite sva polja")
                else:
                    if create_user(new_username, new_password, new_email):
                        # Sačuvaj opštinu
                        set_user_city(new_username, new_municipality)
                        
                        st.success(f"✅ Uspješna registracija! Dobrodošli **{new_username}**!")
                        st.info(f"📍 Vaša opština: **{new_municipality}**")
                        st.balloons()
                        
                        # Automatski prijavi korisnika
                        st.session_state.user = new_username
                        st.session_state.user_city = new_municipality
                        st.rerun()
                    else:
                        st.error("Korisničko ime već postoji")
    
    st.stop()  # Zaustavi izvršavanje dalje - ne prikazuj aplikaciju

# Ako je korisnik prijavljen, nastavi sa aplikacijom

st.markdown("""
<style>
/* Modern professional design */
:root {
    --primary: #667eea;
    --secondary: #764ba2;
    --success: #10b981;
    --warning: #f59e0b;
    --danger: #ef4444;
    --dark: #1f2937;
    --light: #f3f4f6;
}

/* Main header */
.main-header {
    background: linear-gradient(135deg, var(--primary) 0%, var(--secondary) 100%);
    padding: 2rem;
    border-radius: 20px;
    margin-bottom: 2rem;
    box-shadow: 0 10px 30px rgba(102, 126, 234, 0.3);
}

.main-header h1 {
    color: white;
    margin: 0;
    font-size: 2.5rem;
    font-weight: 700;
    text-shadow: 2px 2px 4px rgba(0,0,0,0.2);
}

.main-header p {
    color: rgba(255,255,255,0.9);
    margin: 0.5rem 0 0 0;
    font-size: 1.1rem;
}

/* Cards and badges */
.service-card {
    background: white;
    border-radius: 15px;
    padding: 1.5rem;
    margin: 1rem 0;
    box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    border-left: 4px solid var(--primary);
    transition: transform 0.2s, box-shadow 0.2s;
}

.service-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 15px rgba(0,0,0,0.15);
}

.badge {
    display: inline-block;
    padding: 0.4rem 0.8rem;
    border-radius: 20px;
    font-size: 0.9rem;
    font-weight: 600;
    margin: 0.2rem;
}

.badge-primary { background: #dbeafe; color: #1e40af; }
.badge-success { background: #d1fae5; color: #065f46; }
.badge-warning { background: #fef3c7; color: #92400e; }
.badge-danger { background: #fee2e2; color: #991b1b; }

/* Buttons enhancement */
.stButton > button {
    border-radius: 10px;
    font-weight: 600;
    transition: all 0.3s;
    border: none;
}

.stButton > button:hover {
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

/* Sidebar styling - Modern dark theme */
.css-1d391kg, [data-testid="stSidebar"] {
    background: linear-gradient(180deg, #1a1f2e 0%, #0f1419 100%);
}

[data-testid="stSidebar"] > div:first-child {
    background: linear-gradient(180deg, #1a1f2e 0%, #0f1419 100%);
}

/* Sidebar text colors */
[data-testid="stSidebar"] * {
    color: #e2e8f0 !important;
}

[data-testid="stSidebar"] .stMarkdown {
    color: #e2e8f0;
}

/* Sidebar buttons */
[data-testid="stSidebar"] .stButton > button {
    background: rgba(102, 126, 234, 0.1);
    border: 1px solid rgba(102, 126, 234, 0.3);
    color: #a5b4fc !important;
    transition: all 0.3s;
}

[data-testid="stSidebar"] .stButton > button:hover {
    background: rgba(102, 126, 234, 0.2);
    border-color: rgba(102, 126, 234, 0.5);
    transform: translateX(5px);
}

/* Info boxes */
.stInfo, .stSuccess, .stWarning, .stError {
    border-radius: 12px;
    border-left-width: 5px;
}

/* Chat messages */
.chat-message {
    padding: 1rem;
    border-radius: 12px;
    margin: 0.5rem 0;
    animation: fadeIn 0.3s;
}

@keyframes fadeIn {
    from { opacity: 0; transform: translateY(10px); }
    to { opacity: 1; transform: translateY(0); }
}

/* AI Avatar animacija u chatu */
@keyframes float-avatar {
    0%, 100% { 
        transform: translateY(0px) scale(1);
    }
    50% { 
        transform: translateY(-8px) scale(1.05);
    }
}

@keyframes glow-pulse {
    0%, 100% {
        filter: drop-shadow(0 0 8px rgba(102, 126, 234, 0.4));
    }
    50% {
        filter: drop-shadow(0 0 16px rgba(102, 126, 234, 0.8));
    }
}

/* Animacija za AI avatar u chat porukama */
[data-testid="stChatMessage"][data-testid-type="assistant"] img,
div[data-testid="stChatMessageAvatarAssistant"] img {
    animation: float-avatar 3s ease-in-out infinite, glow-pulse 2s ease-in-out infinite;
    border-radius: 50%;
    border: 2px solid #667eea;
}

.user-message {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    color: white;
    margin-left: 20%;
}

.bot-message {
    background: #f3f4f6;
    color: #1f2937;
    margin-right: 20%;
    border: 1px solid #e5e7eb;
}

/* Mobile responsive */
@media (max-width: 768px) {
    .main-header h1 { font-size: 1.8rem; }
    .main-header { padding: 1.5rem; }
    .service-card { padding: 1rem; }
    .user-message, .bot-message { margin: 0.5rem 0; }
}

/* Map container */
.map-container {
    border-radius: 15px;
    overflow: hidden;
    box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    margin: 1rem 0;
}

/* Stats boxes */
.stat-box {
    background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
    padding: 1.5rem;
    border-radius: 12px;
    text-align: center;
    border: 2px solid #bae6fd;
}

.stat-box h3 {
    color: var(--primary);
    margin: 0;
    font-size: 2rem;
}

.stat-box p {
    color: #64748b;
    margin: 0.5rem 0 0 0;
}
</style>
""", unsafe_allow_html=True)

# Header sa modernim dizajnom
st.markdown("""
<div class="main-header">
    <h1>🇲🇪 MUP Portal Crne Gore</h1>
    <p>Pametni asistent za administrativne usluge i informacije</p>
</div>
""", unsafe_allow_html=True)

rules = load_rules("data/mup_rules.json")

# Učitaj centre na osnovu izabranog grada korisnika
user_city = st.session_state.user_city if st.session_state.user else None
centers = load_centers("data/centers.json", city=user_city)

with st.sidebar:
    # User profile box - Glassmorphism style
    st.markdown(f"""
    <div style="background: rgba(102, 126, 234, 0.15); 
                backdrop-filter: blur(10px);
                border: 1px solid rgba(102, 126, 234, 0.3);
                padding: 1.5rem; 
                border-radius: 20px; 
                margin-bottom: 1.5rem;
                box-shadow: 0 8px 32px 0 rgba(102, 126, 234, 0.2);">
        <div style="display: flex; align-items: center; gap: 1rem;">
            <div style="width: 50px; height: 50px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 50%; display: flex; align-items: center; justify-content: center;
                        font-size: 1.5rem; box-shadow: 0 4px 12px rgba(102, 126, 234, 0.4);">
                👤
            </div>
            <div>
                <h3 style="margin: 0; font-size: 1.3rem; color: #fff; font-weight: 700;">{st.session_state.user}</h3>
                <p style="margin: 0.3rem 0 0 0; color: #a5b4fc; font-size: 0.85rem;">MUP Portal</p>
            </div>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    # Dugme za odjavu
    if st.button("🚪 Odjavi se", use_container_width=True, type="secondary"):
        if os.path.exists("data/session.json"):
            os.remove("data/session.json")
        st.session_state.user = None
        st.session_state.user_city = None
        st.session_state.page = "login"
        st.rerun()
    
    st.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent 0%, rgba(102, 126, 234, 0.3) 50%, transparent 100%); margin: 1.5rem 0;"></div>
    """, unsafe_allow_html=True)
    
    # Učitaj opštinu iz baze ako nije učitana
    if not st.session_state.user_city:
        st.session_state.user_city = get_user_city(st.session_state.user)
    
    # Prikaži opštinu - Modern card
    if st.session_state.user_city:
        st.markdown(f"""
        <style>
            @keyframes pulse-glow {{
                0%, 100% {{ box-shadow: 0 0 20px rgba(59, 130, 246, 0.3); }}
                50% {{ box-shadow: 0 0 35px rgba(59, 130, 246, 0.5); }}
            }}
            .city-card {{
                background: linear-gradient(-45deg, rgba(30, 58, 138, 0.6), rgba(59, 130, 246, 0.6), rgba(102, 126, 234, 0.6));
                background-size: 400% 400%;
                animation: gradientShift 12s ease infinite, pulse-glow 3s ease-in-out infinite;
                backdrop-filter: blur(10px);
            }}
        </style>
        <div class="city-card" style="border: 1px solid rgba(59, 130, 246, 0.4);
                    padding: 1.2rem; 
                    border-radius: 15px;
                    position: relative;
                    overflow: hidden;">
            <div style="position: absolute; top: -20px; right: -20px; width: 80px; height: 80px;
                        background: radial-gradient(circle, rgba(255,255,255,0.15) 0%, transparent 70%);
                        border-radius: 50%;
                        animation: float 5s ease-in-out infinite;"></div>
            <p style="margin: 0; color: #93c5fd; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">📍 Vaša opština</p>
            <p style="margin: 0.5rem 0 0 0; color: #fff; font-size: 1.2rem; font-weight: 700;">
                {st.session_state.user_city}
            </p>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("⚠️ Opština nije postavljena")
    
    st.markdown("""
    <div style="height: 1px; background: linear-gradient(90deg, transparent 0%, rgba(102, 126, 234, 0.3) 50%, transparent 100%); margin: 1.5rem 0;"></div>
    """, unsafe_allow_html=True)
    
    # Settings header sa ikonom
    st.markdown("""
    <div style="margin-bottom: 1rem;">
        <h3 style="color: #fff; font-size: 1.1rem; font-weight: 700; margin: 0;">
            ⚙️ Podešavanja simulacije
        </h3>
        <p style="color: #94a3b8; font-size: 0.8rem; margin: 0.3rem 0 0 0;">
            Queue teorija parametri
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    arrival = st.slider("Dolazaka na sat (λ)", 5, 40, 18)
    service = st.slider("Usluženi na sat (μ)", 5, 40, 20)
    qsize = st.slider("Trenutno u redu", 0, 40, 12)

# Moderni toggle buttons
st.markdown("""
<div style="background: #f8fafc; padding: 0.5rem; border-radius: 15px; margin: 1.5rem 0;">
</div>
""", unsafe_allow_html=True)

col_mode1, col_mode2 = st.columns(2, gap="medium")
with col_mode1:
    button_style = "primary" if st.session_state.chat_mode else "secondary"
    if st.button("💬 AI Chatbot", use_container_width=True, type=button_style):
        st.session_state.chat_mode = True
        # Resetuj kontekst i istoriju chat-a
        st.session_state.chat_messages = []
        st.session_state.conversation_context = {}
        st.rerun()
with col_mode2:
    button_style = "primary" if not st.session_state.chat_mode else "secondary"
    if st.button("🔍 Klasična Pretraga", use_container_width=True, type=button_style):
        st.session_state.chat_mode = False
        # Resetuj kontekst i istoriju chat-a
        st.session_state.chat_messages = []
        st.session_state.conversation_context = {}
        st.rerun()

st.markdown("<br>", unsafe_allow_html=True)

# Preuzmi historiju upita SAMO za AI Chat mod (ne za klasičnu pretragu)
previous_queries = []
if st.session_state.user and st.session_state.chat_mode:
    history = get_user_queries(st.session_state.user, limit=10)
    previous_queries = [item['query'] for item in history]

# AI CHATBOT MOD
if st.session_state.chat_mode:
    st.subheader("🤖 AI Chatbot Asistent")
    
    # Privremeno isključi OpenAI zbog API limita - koristi samo fallback
    openai_ready = False  # Biće True kada dobiješ novi API key
    
    if not openai_ready:
        st.info("🤖 Koristim napredni keyword matching sistem (bez OpenAI API-ja)")
        st.caption("💡 Pitaj me o: ličnoj karti, pašošu, vozačkoj dozvoli, promjeni prebivališta")
    
    # Custom CSS za animaciju avatara - primjenjuje se na sve elemente u kontejneru
    st.markdown("""
    <style>
    /* Forsiraj animaciju na sve slike u chat containeru */
    .stChatMessage img[alt*="avatar"] {
        animation: float-avatar 3s ease-in-out infinite !important;
        filter: drop-shadow(0 0 12px rgba(102, 126, 234, 0.6)) !important;
        border: 3px solid #667eea !important;
        border-radius: 50% !important;
    }
    
    /* Specifično za assistant poruke */
    [data-testid="chatAvatarIcon-assistant"] img,
    [data-testid="stChatMessageAvatarAssistant"] img {
        animation: float-avatar 3s ease-in-out infinite, glow-pulse 2s ease-in-out infinite !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Chat container
    chat_container = st.container(height=400)
    
    # Prikaz chat historije
    with chat_container:
        if not st.session_state.chat_messages:
            # Animated welcome message
            st.markdown(f"""
            <div style='padding: 2rem; background: linear-gradient(135deg, #667eea15, #764ba215); 
                        border-radius: 16px; animation: fadeIn 0.8s; text-align: center; 
                        border: 2px dashed #667eea50;'>
                <h2 style='color: #667eea; margin: 0 0 1rem 0;'>👋 Dobrodošli{', ' + st.session_state.user if st.session_state.user else ''}!</h2>
                <p style='font-size: 1.1rem; color: #555; margin: 0;'>
                    Pitajte me bilo šta o MUP uslugama<br>
                    <small style='color: #888;'>Lična karta • Pasoš • Vozačka dozvola • Promjena prebivališta</small>
                </p>
            </div>
            """, unsafe_allow_html=True)
        
        for msg in st.session_state.chat_messages:
            # Custom avatari
            if msg["role"] == "user":
                avatar = "👤"
            else:
                # Koristi custom AI avatar sliku
                avatar = ai_avatar
            with st.chat_message(msg["role"], avatar=avatar):
                st.markdown(msg["content"])
    
    # Prikaži mapu u chatu ako je zatraženo
    if st.session_state.get('show_map_in_chat', False):
        with chat_container:
            st.markdown("---")
            
            if centers:
                # Izračunaj centar mape
                avg_lat = sum(c["lat"] for c in centers) / len(centers)
                avg_lon = sum(c["lon"] for c in centers) / len(centers)
                
                # Kreiraj mapu
                m = folium.Map(
                    location=[avg_lat, avg_lon],
                    zoom_start=10,
                    tiles="OpenStreetMap"
                )
                
                # Dodaj markere
                for idx, c in enumerate(centers):
                    popup_html = f"""
                    <div style="font-family: Arial; min-width: 200px;">
                        <h4 style="margin: 0 0 8px 0; color: #1e40af;">{c['naziv']}</h4>
                        <p style="margin: 4px 0;"><b>🕒 Radno vrijeme:</b><br>{c['radno_vrijeme']}</p>
                        <a href="{google_maps_link(c['lat'], c['lon'], c['naziv'])}" 
                           target="_blank" 
                           style="display: inline-block; margin-top: 8px; padding: 6px 12px; 
                                  background: #2563eb; color: white; text-decoration: none; 
                                  border-radius: 6px; font-weight: bold;">
                            📍 Otvori u Google Maps
                        </a>
                    </div>
                    """
                    
                    icon_color = 'red' if idx == 0 else 'blue'
                    
                    folium.Marker(
                        location=[c["lat"], c["lon"]],
                        popup=folium.Popup(popup_html, max_width=300),
                        tooltip=c["naziv"],
                        icon=folium.Icon(color=icon_color, icon='info-sign')
                    ).add_to(m)
                
                st_folium(m, width=600, height=350, returned_objects=[])
                
                # Lista centara
                st.caption("**📍 MUP centri:**")
                for c in centers:
                    link = google_maps_link(c["lat"], c["lon"], c["naziv"])
                    st.markdown(f"• **{c['naziv']}** - {c['radno_vrijeme']} [Google Maps]({link})")
    
    # Input za novu poruku
    if prompt := st.chat_input("Ukucaj pitanje..."):
        # Dodaj korisničku poruku
        st.session_state.chat_messages.append({"role": "user", "content": prompt})
        
        # Prikazi korisničku poruku
        with chat_container:
            with st.chat_message("user", avatar="👤"):
                st.markdown(prompt)
        
        # Generiši AI odgovor
        with chat_container:
            with st.chat_message("assistant", avatar=ai_avatar):
                # Enhanced loading animation with skeleton
                import time
                placeholder = st.empty()
                
                # Skeleton loader
                with placeholder.container():
                    st.markdown("""
                    <div style="padding: 1rem;">
                        <div class="skeleton" style="height: 20px; width: 80%; margin-bottom: 10px;"></div>
                        <div class="skeleton" style="height: 20px; width: 60%; margin-bottom: 10px;"></div>
                        <div class="skeleton" style="height: 20px; width: 90%;"></div>
                    </div>
                    """, unsafe_allow_html=True)
                    
                loading_messages = [
                    "🤔 Analiziram upit...",
                    "🔍 Tražim informacije u bazi...",
                    "⚡ Pripremam personalizovan odgovor..."
                ]
                
                for idx, msg in enumerate(loading_messages):
                    time.sleep(0.4)
                    placeholder.markdown(f"<div style='padding: 0.5rem; animation: fadeIn 0.3s;'><i>{msg}</i></div>", unsafe_allow_html=True)
                
                if openai_ready:
                    # Koristi pravi AI
                    ai_response = chat_with_ai(
                        st.session_state.chat_messages,
                        rules,
                        centers
                    )
                else:
                    # Fallback na keyword matching sa kontekstom
                    from ai_chatbot import get_smart_response
                    ai_response = get_smart_response(
                        prompt, 
                        rules, 
                        centers,
                        st.session_state.conversation_context,
                        st.session_state.user_city
                    )
                
                placeholder.empty()
                st.markdown(ai_response)
        
        # Dodaj AI odgovor u historiju
        st.session_state.chat_messages.append({"role": "assistant", "content": ai_response})
        
        # Detektuj pitanje o lokaciji i automatski prikaži/sakrij mapu
        from ai_chatbot import normalize_text
        prompt_normalized = normalize_text(prompt.lower())
        if any(word in prompt_normalized for word in ["gdje", "gde", "adres", "centar", "mup", "lokacij", "najbliz", "bliz"]):
            st.session_state.show_map_in_chat = True
        else:
            # Ako pitanje nije o lokaciji, sakrij mapu
            st.session_state.show_map_in_chat = False
        
        # Detektuj servis iz ovog pitanja
        detected_service = detect_service(prompt, rules)
        if detected_service:
            st.session_state.current_service = detected_service
            st.session_state.conversation_context['last_service'] = detected_service
            
            # Sačuvaj upit u bazu
            if st.session_state.user:
                save_query(st.session_state.user, prompt, detected_service)
        
        st.rerun()
    
    # Smart suggestions - prikaži relevantne quick actions sa animacijom
    if st.session_state.chat_messages and st.session_state.current_service:
        st.markdown("""
        <style>
        @keyframes pulse-glow {
            0%, 100% { box-shadow: 0 0 10px rgba(102, 126, 234, 0.3); }
            50% { box-shadow: 0 0 20px rgba(102, 126, 234, 0.6); }
        }
        </style>
        """, unsafe_allow_html=True)
        st.markdown("---")
        st.markdown("""
        <div style='padding: 0.5rem; animation: fadeIn 0.5s;'>
            <p style='margin: 0; color: #667eea; font-weight: 600;'>💡 Brze akcije:</p>
        </div>
        """, unsafe_allow_html=True)
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            if st.button("📍 Vidi na mapi", use_container_width=True):
                # Prikaži mapu direktno u chatu
                st.session_state.chat_messages.append({
                    "role": "assistant",
                    "content": "📍 **Prikaz MUP centara na mapi**"
                })
                st.session_state.show_map_in_chat = True
                st.rerun()
        
        with col2:
            if st.button("📥 Preuzmi dokument", use_container_width=True):
                service_info = rules[st.session_state.current_service]
                service_details = {
                    'cijena': f"{service_info['taksa_eur']:.2f} €",
                    'trajanje': f"{service_info['rok_izrade_dana']} dana",
                    'potrebni_dokumenti': service_info['dokumenta']
                }
                docx_buffer = generate_docx_confirmation(
                    user_name=st.session_state.user,
                    user_email=get_user_email(st.session_state.user),
                    service_name=st.session_state.current_service,
                    service_details=service_details,
                    center_name=centers[0]["naziv"],
                    center_address=centers[0]["naziv"]
                )
                filename = f"potvrda_{st.session_state.current_service.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                st.download_button(
                    "📥 Preuzmi Word",
                    docx_buffer,
                    file_name=filename,
                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    use_container_width=True
                )
        
        with col3:
            if st.button("📊 Procjena čekanja", use_container_width=True):
                est = estimate_wait_minutes(arrival, service, qsize)
                slot = next_best_slot(datetime.now(), est)
                st.session_state.chat_messages.append({
                    "role": "assistant", 
                    "content": f"⏱️ **Procjena čekanja**: ~{est} minuta\n\n📅 **Predloženi termin**: {slot.strftime('%d.%m.%Y u %H:%M')}"
                })
                st.rerun()
        
        with col4:
            if st.button("💬 Related pitanja", use_container_width=True):
                st.session_state.show_suggestions = True
                st.rerun()
    
    # Prikaži klikabilne suggestion dugmiće sa animacijom
    if st.session_state.get('show_suggestions', False) and st.session_state.current_service:
        st.markdown("""
        <div style='animation: fadeIn 0.5s; padding: 1rem; background: linear-gradient(135deg, #f0f9ff, #e0f2fe); 
                    border-radius: 12px; margin: 1rem 0; border: 1px solid #bae6fd;'>
            <p style='margin: 0; color: #0369a1; font-weight: 600;'>💡 Predložena pitanja - klikni za brz odgovor:</p>
        </div>
        """, unsafe_allow_html=True)
        
        service_acc = get_accusative_form(st.session_state.current_service)
        
        suggestions = [
            f"Koliko košta {st.session_state.current_service}?",
            f"Gdje da uplatim {service_acc}?",
            f"Koja dokumenta trebaju?",
            f"Gdje je najbliži MUP?"
        ]
        
        cols = st.columns(2)
        for idx, suggestion in enumerate(suggestions):
            with cols[idx % 2]:
                if st.button(suggestion, key=f"suggest_{idx}", use_container_width=True):
                    # Automatski pošalji pitanje
                    st.session_state.chat_messages.append({"role": "user", "content": suggestion})
                    
                    # Generiši odgovor
                    from ai_chatbot import get_smart_response
                    ai_response = get_smart_response(
                        suggestion, 
                        rules, 
                        centers,
                        st.session_state.conversation_context,
                        st.session_state.user_city
                    )
                    st.session_state.chat_messages.append({"role": "assistant", "content": ai_response})
                    
                    st.session_state.show_suggestions = False
                    st.rerun()
    
    # Action buttons
    col_a, col_b = st.columns(2)
    with col_a:
        if st.session_state.chat_messages:
            if st.button("🗑️ Obriši chat", use_container_width=True):
                st.session_state.chat_messages = []
                st.session_state.current_service = None
                st.session_state.conversation_context = {}
                st.rerun()
    
    with col_b:
        if st.session_state.chat_messages and len(st.session_state.chat_messages) > 2:
            # Export conversation to text
            conversation_text = "\n\n".join([
                f"{'Korisnik' if msg['role'] == 'user' else 'Asistent'}: {msg['content']}"
                for msg in st.session_state.chat_messages
            ])
            st.download_button(
                "📄 Eksportuj razgovor",
                conversation_text,
                file_name=f"chat_conversation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
                mime="text/plain",
                use_container_width=True
            )

# KLASIČNA PRETRAGA
else:
    st.subheader("💬 Postavi pitanje")

    # Funkcija za pretraživanje koja filtrira opcije (cached za bolju performansu)
    @st.cache_data(show_spinner=False)
    def search_queries_cached(searchterm: str, prev_queries_tuple):
        from utils import normalize_text
        
        previous_queries = list(prev_queries_tuple)  # Convert tuple back to list
        
        if not searchterm:
            # Ako je prazan unos, vrati sve osnovne usluge + istoriju
            base_services = [
                "pasoš", 
                "lična karta", 
                "vozačka dozvola", 
                "promjena prebivališta"
            ]
            return previous_queries + base_services
        
        # Kombiniraj prethodne upite i osnovne usluge
        all_options = previous_queries + [
            "pasoš", 
            "lična karta", 
            "vozačka dozvola", 
            "promjena prebivališta"
        ]
        
        # Filtriraj opcije koristeći normalize_text za akcent-insenzitivno pretraživanje
        searchterm_normalized = normalize_text(searchterm)
        filtered = [opt for opt in all_options if searchterm_normalized in normalize_text(opt)]
        
        # Ukloni duplikate ali zadrži redoslijed
        seen = set()
        result = []
        for item in filtered:
            normalized = normalize_text(item)
            if normalized not in seen:
                seen.add(normalized)
                result.append(item)
        
        return result[:10]  # Vrati maksimalno 10 rezultata
    
    # Wrapper funkcija za st_searchbox (mora biti non-cached)
    def search_queries(searchterm: str, **kwargs):
        return search_queries_cached(searchterm, tuple(previous_queries))

    # Autocomplete search box - SAMO za klasičnu pretragu sa debouncing
    query = st_searchbox(
        search_queries,
        placeholder="Ukucaj npr. 'p' za pasoš, 'pre' za prebivalište...",
        clear_on_submit=False,
        rerun_on_update=False,  # Spriječi auto-rerun na svaku promjenu
        debounce=300,  # Čeka 300ms prije search-a (smanjuje flikering)
        key="query_searchbox"
    )

    if query:
        found = detect_service(query, rules)
        if found is None:
            st.warning("Nisam siguran o kojoj usluzi je riječ. Pokušaj sa: lična karta, pasoš, vozačka dozvola.")
        else:
            # Sačuvaj upit u bazu
            if st.session_state.user:
                save_query(st.session_state.user, query, found)
            
            info = rules[found]
            est = estimate_wait_minutes(arrival, service, qsize)
            slot = next_best_slot(datetime.now(), est)
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("💶 Taksa", f"{info['taksa_eur']:.2f} €")
            with col2:
                st.metric("⏱️ Rok izrade", f"{info['rok_izrade_dana']} dana")
            with col3:
                st.metric("📊 Čekanje", f"~{est} min")

            with st.container(border=True):
                st.markdown("#### 📄 Potrebna dokumenta")
                for d in info["dokumenta"]:
                    st.markdown(f"- {d}")

            with st.container(border=True):
                st.markdown("#### 🏦 Podaci za uplatu")
                st.info(info['uplata'])

            with st.container(border=True):
                st.markdown("#### 📍 Najbliži MUP centri")
                
                # Kreiraj interaktivnu mapu
                if centers:
                    # Cache map creation to prevent flickering
                    if 'map_created' not in st.session_state or st.session_state.get('map_city') != st.session_state.user_city:
                        # Izračunaj centar mape (prosek svih lokacija)
                        avg_lat = sum(c["lat"] for c in centers) / len(centers)
                        avg_lon = sum(c["lon"] for c in centers) / len(centers)
                        
                        # Kreiraj mapu
                        m = folium.Map(
                            location=[avg_lat, avg_lon],
                            zoom_start=10,
                            tiles="OpenStreetMap"
                        )
                        
                        # Dodaj markere za sve centre
                        for idx, c in enumerate(centers):
                            # Kreiraj popup sa informacijama
                            popup_html = f"""
                            <div style="font-family: Arial; min-width: 200px;">
                                <h4 style="margin: 0 0 8px 0; color: #1e40af;">{c['naziv']}</h4>
                                <p style="margin: 4px 0;"><b>🕒 Radno vrijeme:</b><br>{c['radno_vrijeme']}</p>
                                <p style="margin: 4px 0;"><b>⏱️ Čekanje:</b> ~{est} min</p>
                                <a href="{google_maps_link(c['lat'], c['lon'], c['naziv'])}" 
                                   target="_blank" 
                                   style="display: inline-block; margin-top: 8px; padding: 6px 12px; 
                                          background: #2563eb; color: white; text-decoration: none; 
                                          border-radius: 6px; font-weight: bold;">
                                    📍 Otvori u Google Maps
                                </a>
                            </div>
                            """
                            
                            # Različite boje za prvi centar (najbliži)
                            icon_color = 'red' if idx == 0 else 'blue'
                            
                            folium.Marker(
                                location=[c["lat"], c["lon"]],
                                popup=folium.Popup(popup_html, max_width=300),
                                tooltip=c["naziv"],
                                icon=folium.Icon(color=icon_color, icon='info-sign')
                            ).add_to(m)
                        
                        st.session_state.map_created = m
                        st.session_state.map_city = st.session_state.user_city
                
                    # Prikaži mapu iz cache-a
                    st_folium(st.session_state.map_created, width=700, height=400, returned_objects=[])
                    
                    # Lista centara ispod mape
                    st.markdown("---")
                    for c in centers:
                        link = google_maps_link(c["lat"], c["lon"], c["naziv"])
                        col_a, col_b = st.columns([3, 1])
                        with col_a:
                            st.markdown(f"**{c['naziv']}**")
                            st.caption(f"🕒 {c['radno_vrijeme']}")
                        with col_b:
                            st.link_button("📍 Google Maps", link, use_container_width=True)

            with st.container(border=True):
                st.markdown("#### 🎯 Predloženi termin dolaska")
                
                # Toggle za HPC vs Basic predviđanje
                use_hpc = st.checkbox("🚀 Koristi HPC predviđanje (Monte Carlo simulacija)", value=False, 
                                      help="HPC analizira 5000 scenarija paralelno na svim CPU cores za tačniju preporuku")
                
                if use_hpc:
                    # Cool HPC loading animacija
                    import time
                    progress_placeholder = st.empty()
                    status_placeholder = st.empty()
                    
                    hpc_steps = [
                        ("🔧 Inicijalizacija HPC okruženja...", "Povezujem se na HPC resurse"),
                        ("🧮 Generisanje Monte Carlo scenarija...", "Kreiram 5000 različitih scenarija"),
                        ("⚡ Paralelno izvršavanje na CPU cores...", f"Koristim {os.cpu_count()} CPU jezgara"),
                        ("📊 Analiza rezultata...", "Analiziram optimalne vremenske slotove"),
                        ("✅ Gotovo!", "HPC simulacija završena uspješno")
                    ]
                    
                    progress_bar = progress_placeholder.progress(0)
                    
                    for idx, (step, detail) in enumerate(hpc_steps):
                        # Animated progress message
                        status_placeholder.markdown(f"""
                        <div style='padding: 1rem; background: linear-gradient(135deg, #667eea15, #764ba215); 
                                    border-radius: 12px; border-left: 4px solid #667eea; animation: fadeIn 0.3s;'>
                            <strong style='color: #667eea;'>{step}</strong><br>
                            <small style='color: #666;'>{detail}</small>
                        </div>
                        """, unsafe_allow_html=True)
                        progress_bar.progress((idx + 1) / len(hpc_steps))
                        
                        if idx < len(hpc_steps) - 1:
                            time.sleep(0.5)
                        else:
                            time.sleep(0.3)
                    
                    # Preuzmi radno vrijeme prvog centra
                    working_hours = centers[0]["radno_vrijeme"] if centers else "08:00-15:00"
                    
                    # Pokreni HPC predviđanje
                    hpc_result = predict_best_arrival_time(
                        arrival_rate=arrival,
                        service_rate=service,
                        current_queue=qsize,
                        working_hours=working_hours,
                        num_simulations=5000
                    )
                    
                    progress_placeholder.empty()
                    status_placeholder.empty()
                    
                    # Prikaži HPC rezultate
                    col_hpc1, col_hpc2, col_hpc3 = st.columns(3)
                    with col_hpc1:
                        st.metric("⏰ Optimalno vrijeme", 
                                 hpc_result.get('recommended_time', datetime.now()).strftime('%H:%M'))
                    with col_hpc2:
                        st.metric("⌛ Prosječno čekanje", 
                                 f"{hpc_result.get('estimated_wait_avg', 0)} min")
                    with col_hpc3:
                        st.metric("👥 Očekivan red", 
                                 f"{hpc_result.get('queue_size_avg', 0)} ljudi")
                    
                    # Success message with animation
                    if 'recommended_time' in hpc_result:
                        st.markdown(f"""
                        <div style='padding: 1.5rem; background: linear-gradient(135deg, #10b98115, #34d39915); 
                                    border-radius: 12px; border-left: 4px solid #10b981; animation: fadeIn 0.5s; margin: 1rem 0;'>
                            <h3 style='color: #10b981; margin: 0;'>✅ Optimalno vrijeme pronađeno!</h3>
                            <p style='font-size: 1.3rem; font-weight: bold; margin: 0.5rem 0 0 0;'>
                                📅 {hpc_result['recommended_time'].strftime('%d.%m.%Y u %H:%M')}
                            </p>
                        </div>
                        """, unsafe_allow_html=True)
                    
                    # Detaljna statistika
                    if 'estimated_wait_range' in hpc_result:
                        with st.expander("📊 Detaljna HPC statistika", expanded=False):
                            st.markdown(f"""
                            - **Raspon čekanja:** {hpc_result.get('estimated_wait_range', (0, 0))[0]}-{hpc_result.get('estimated_wait_range', (0, 0))[1]} minuta
                        - **50% ljudi čeka max:** {hpc_result.get('percentile_50', 0)} min
                        - **95% ljudi čeka max:** {hpc_result.get('percentile_95', 0)} min
                        - **Pouzdanost:** {hpc_result.get('confidence', 0)}% confidence interval
                        - **Broj simulacija:** 5,000 Monte Carlo scenarija
                        - **Metoda:** Parallel processing na {os.cpu_count()} CPU cores
                        """)
                    
                        st.caption("🎯 HPC preporuka zasnovana na 5,000 paralelnih simulacija")
                else:
                    # Basic predviđanje (stara metoda)
                    st.success(f"**{slot.strftime('%d.%m.%Y u %H:%M')}**")
                    st.caption("💡 Osnovna procjena zasnovana na trenutnom opterećenju")
                
                # Word dokument download dugme - samo za prijavljene korisnike
                if st.session_state.user and centers:
                    # Pripremi podatke za dokument - koristi PRAVE ključeve iz info objekta
                    service_details = {
                        'cijena': f"{info['taksa_eur']:.2f} €",
                        'trajanje': f"{info['rok_izrade_dana']} dana",
                        'potrebni_dokumenti': info['dokumenta']
                    }
                    
                    # Generiši Word dokument
                    docx_buffer = generate_docx_confirmation(
                        user_name=st.session_state.user,
                        user_email=get_user_email(st.session_state.user),
                        service_name=found,
                        service_details=service_details,
                        center_name=centers[0]["naziv"],
                        center_address=centers[0]["naziv"]
                    )
                    
                    # Download dugme - automatski preuzimanje
                    filename = f"potvrda_{found.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.docx"
                    st.download_button(
                        "📥 Preuzmi Word dokument",
                        docx_buffer,
                        file_name=filename,
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        use_container_width=True
                    )
                else:
                    st.info("🔐 Prijavite se da preuzmete Word dokument")

# ============================================
# ANALYTICS DASHBOARD - Dropdown sekcija na dnu
# ============================================
if st.session_state.user:
    st.markdown("<br><br>", unsafe_allow_html=True)
    
    # Import analytics funkcija
    from analytics import get_analytics_summary, create_service_pie_chart, create_peak_hours_chart
    
    # Expander sa custom stilom i ikonom
    with st.expander("📊 **Analytics Dashboard** - Klikni za statistiku korišćenja portala", expanded=False):
        # Header unutar expandera
        st.markdown("""
        <div style='text-align: center; padding: 1.5rem; background: linear-gradient(135deg, #667eea, #764ba2); 
                    border-radius: 15px; margin: 1rem 0; animation: fadeIn 0.6s; box-shadow: 0 8px 30px rgba(102, 126, 234, 0.25);'>
            <h2 style='color: white; margin: 0; font-size: 2rem;'>📊 Analytics Dashboard</h2>
            <p style='color: rgba(255,255,255,0.9); margin: 0.3rem 0 0 0;'>Statistika se automatski ažurira nakon svake pretrage</p>
        </div>
        """, unsafe_allow_html=True)
        
        # Summary metrics - 4 velike kartice (fresh data svaki put)
        stats = get_analytics_summary()
        
        st.markdown("### 📈 Pregled sistema")
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("""
            <div style='padding: 1.5rem; background: linear-gradient(135deg, #667eea15, #764ba215); 
                        border-radius: 15px; text-align: center; border: 2px solid #667eea30;'>
                <p style='font-size: 2.5rem; margin: 0;'>👥</p>
                <p style='font-size: 2rem; font-weight: bold; color: #667eea; margin: 0.5rem 0;'>{}</p>
                <p style='color: #888; margin: 0;'>Ukupno korisnika</p>
            </div>
            """.format(stats['total_users']), unsafe_allow_html=True)
        
        with col2:
            st.markdown("""
            <div style='padding: 1.5rem; background: linear-gradient(135deg, #f093fb15, #f5576c15); 
                        border-radius: 15px; text-align: center; border: 2px solid #f093fb30;'>
                <p style='font-size: 2.5rem; margin: 0;'>📊</p>
                <p style='font-size: 2rem; font-weight: bold; color: #f093fb; margin: 0.5rem 0;'>{}</p>
                <p style='color: #888; margin: 0;'>Ukupno upita</p>
            </div>
            """.format(stats['total_queries']), unsafe_allow_html=True)
        
        with col3:
            st.markdown("""
            <div style='padding: 1.5rem; background: linear-gradient(135deg, #4facfe15, #00f2fe15); 
                        border-radius: 15px; text-align: center; border: 2px solid #4facfe30;'>
                <p style='font-size: 2.5rem; margin: 0;'>📅</p>
                <p style='font-size: 2rem; font-weight: bold; color: #4facfe; margin: 0.5rem 0;'>{}</p>
                <p style='color: #888; margin: 0;'>Upita danas</p>
            </div>
            """.format(stats['queries_today']), unsafe_allow_html=True)
        
        with col4:
            st.markdown("""
            <div style='padding: 1.5rem; background: linear-gradient(135deg, #43e97b15, #38f9d715); 
                        border-radius: 15px; text-align: center; border: 2px solid #43e97b30;'>
                <p style='font-size: 2.5rem; margin: 0;'>🏆</p>
                <p style='font-size: 1.5rem; font-weight: bold; color: #43e97b; margin: 0.5rem 0;'>{}</p>
                <p style='color: #888; margin: 0;'>Top korisnik</p>
            </div>
            """.format(stats['top_user']), unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        
        # Grafici u 2 kolone (lado po lado)
        st.markdown("### 📊 Detaljne statistike")
        
        col_chart1, col_chart2 = st.columns(2)
        
        with col_chart1:
            st.markdown("""
            <div style='padding: 1rem; background: rgba(102, 126, 234, 0.05); border-radius: 12px; margin-bottom: 1rem;'>
                <h4 style='color: #667eea; margin: 0;'>📊 Najpopularnije usluge</h4>
                <p style='color: #888; font-size: 0.85rem; margin: 0.3rem 0 0 0;'>Distribucija po tipu usluge</p>
            </div>
            """, unsafe_allow_html=True)
            fig = create_service_pie_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("📭 Nema podataka")
        
        with col_chart2:
            st.markdown("""
            <div style='padding: 1rem; background: rgba(79, 172, 254, 0.05); border-radius: 12px; margin-bottom: 1rem;'>
                <h4 style='color: #4facfe; margin: 0;'>⏰ Peak Hours</h4>
                <p style='color: #888; font-size: 0.85rem; margin: 0.3rem 0 0 0;'>Aktivnost tokom dana</p>
            </div>
            """, unsafe_allow_html=True)
            fig = create_peak_hours_chart()
            if fig:
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("📭 Nema podataka")
 
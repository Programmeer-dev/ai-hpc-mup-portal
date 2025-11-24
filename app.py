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
from ai_chatbot import chat_with_ai, init_openai, get_fallback_response
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

init_db()

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

# Custom CSS za login stranicu
st.markdown("""
<style>

    /* Login page styling */
    .login-header {
        text-align: center;
        padding: 2rem 0;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        border-radius: 15px;
        margin-bottom: 2rem;
        color: white;
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
    .stTabs [data-baseweb="tab-list"] {
        gap: 2rem;
        justify-content: center;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 1rem 2rem;
        font-size: 1.1rem;
        font-weight: 600;
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
                        st.success("Uspješna prijava!")
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
        <div style="background: rgba(59, 130, 246, 0.1); 
                    backdrop-filter: blur(10px);
                    border: 1px solid rgba(59, 130, 246, 0.3);
                    padding: 1.2rem; 
                    border-radius: 15px;
                    position: relative;
                    overflow: hidden;">
            <div style="position: absolute; top: -20px; right: -20px; width: 80px; height: 80px;
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        border-radius: 50%; opacity: 0.1;"></div>
            <p style="margin: 0; color: #60a5fa; font-weight: 600; font-size: 0.85rem; text-transform: uppercase; letter-spacing: 1px;">📍 Vaša opština</p>
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

# Preuzmi historiju upita ako je korisnik prijavljen
previous_queries = []
if st.session_state.user:
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
    
    # Chat container
    chat_container = st.container(height=400)
    
    # Prikaz chat historije
    with chat_container:
        if not st.session_state.chat_messages:
            st.info("👋 Zdravo! Pitaj me bilo šta o MUP uslugama - ličnoj karti, pašošu, vozačkoj dozvoli...")
        
        for msg in st.session_state.chat_messages:
            # Custom avatari
            avatar = "👤" if msg["role"] == "user" else "🤖"
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
        
        st.session_state.show_map_in_chat = False
    
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
            with st.chat_message("assistant", avatar="🤖"):
                # Cool loading animacija
                loading_messages = [
                    "🤔 Analiziram upit...",
                    "🔍 Tražim informacije...",
                    "⚡ Pripremam odgovor..."
                ]
                import time
                placeholder = st.empty()
                
                for msg in loading_messages:
                    placeholder.markdown(f"*{msg}*")
                    time.sleep(0.3)
                
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
        
        # Detektuj servis iz ovog pitanja
        detected_service = detect_service(prompt, rules)
        if detected_service:
            st.session_state.current_service = detected_service
            st.session_state.conversation_context['last_service'] = detected_service
            
            # Sačuvaj upit u bazu
            if st.session_state.user:
                save_query(st.session_state.user, prompt, detected_service)
        
        st.rerun()
    
    # Smart suggestions - prikaži relevantne quick actions
    if st.session_state.chat_messages and st.session_state.current_service:
        st.markdown("---")
        st.caption("💡 Brze akcije:")
        
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
    
    # Prikaži klikabilne suggestion dugmiće
    if st.session_state.get('show_suggestions', False) and st.session_state.current_service:
        st.markdown("---")
        st.caption("💡 Klikni na pitanje:")
        
        suggestions = [
            f"Koliko košta {st.session_state.current_service}?",
            f"Gdje da uplatim {st.session_state.current_service}?",
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

# Funkcija za pretraživanje koja filtrira opcije
def search_queries(searchterm: str, **kwargs):
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
    
    # Filtriraj opcije koje sadrže searchterm (case insensitive)
    searchterm_lower = searchterm.lower()
    filtered = [opt for opt in all_options if searchterm_lower in opt.lower()]
    
    # Ukloni duplikate ali zadrži redoslijed
    seen = set()
    result = []
    for item in filtered:
        if item.lower() not in seen:
            seen.add(item.lower())
            result.append(item)
    
    return result[:10]  # Vrati maksimalno 10 rezultata

# Autocomplete search box
query = st_searchbox(
    search_queries,
    placeholder="Ukucaj npr. 'p' za pasoš, 'pre' za prebivalište...",
    clear_on_submit=False,
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
                    "🔧 Inicijalizacija HPC okruženja...",
                    "🧮 Generisanje Monte Carlo scenarija...",
                    "⚡ Paralelno izvršavanje na CPU cores...",
                    "📊 Analiza rezultata...",
                    "✅ Gotovo!"
                ]
                
                progress_bar = progress_placeholder.progress(0)
                
                for idx, step in enumerate(hpc_steps):
                    status_placeholder.info(step)
                    progress_bar.progress((idx + 1) / len(hpc_steps))
                    
                    if idx < len(hpc_steps) - 1:  # Ne čekaj nakon zadnjeg koraka
                        time.sleep(0.4)
                
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
                             hpc_result['recommended_time'].strftime('%H:%M'))
                with col_hpc2:
                    st.metric("⌛ Prosječno čekanje", 
                             f"{hpc_result['estimated_wait_avg']} min")
                with col_hpc3:
                    st.metric("👥 Očekivan red", 
                             f"{hpc_result['queue_size_avg']} ljudi")
                
                st.success(f"**📅 {hpc_result['recommended_time'].strftime('%d.%m.%Y u %H:%M')}**")
                
                # Detaljna statistika
                with st.expander("📊 Detaljna HPC statistika"):
                    st.markdown(f"""
                    - **Raspon čekanja:** {hpc_result['estimated_wait_range'][0]}-{hpc_result['estimated_wait_range'][1]} minuta
                    - **50% ljudi čeka max:** {hpc_result['percentile_50']} min
                    - **95% ljudi čeka max:** {hpc_result['percentile_95']} min
                    - **Pouzdanost:** {hpc_result['confidence']}% confidence interval
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
 
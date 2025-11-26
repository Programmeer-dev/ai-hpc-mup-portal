"""
Analytics modul za MUP Portal - kreiranje grafika i vizualizacija
OBJAŠNJENJE: Ovaj fajl sadrži funkcije koje kreiraju Plotly grafike iz podataka
"""

import plotly.graph_objects as go
import plotly.express as px
from database.database import get_service_stats, get_queries_by_time, get_total_stats

def create_service_pie_chart():
    """
    Kreira PIE CHART za najpopularnije usluge
    OBJAŠNJENJE: 
    - Izvlačimo podatke iz baze (koliko puta je svaka usluga pretražena)
    - Plotly pravi "kolač" dijagram gdje je veličina isječka = broj pretraga
    """
    data = get_service_stats()
    
    if not data:
        return None
    
    # Izvlačimo labele (imena usluga) i values (broj pretraga)
    labels = [item['service'] for item in data]
    values = [item['count'] for item in data]
    
    # Kreiramo pie chart sa custom bojama
    fig = go.Figure(data=[go.Pie(
        labels=labels,
        values=values,
        hole=0.4,  # Pravi "donut" efekat (rupa u sredini)
        marker=dict(
            colors=['#667eea', '#764ba2', '#f093fb', '#4facfe', '#43e97b', '#ff6b6b', '#feca57'],
            line=dict(color='white', width=2)
        ),
        textinfo='percent',  # Prikazuj SAMO procenat
        textfont=dict(size=16, color='white'),
        textposition='inside',
        hovertemplate='<b>%{label}</b><br>Upita: %{value}<br>Procenat: %{percent}<extra></extra>'
    )])
    
    fig.update_layout(
        title={
            'text': '📊 Najpopularnije MUP usluge',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#667eea'}
        },
        showlegend=True,  # Legenda sa strane pokazuje imena
        legend=dict(
            orientation="v",
            yanchor="middle",
            y=0.5,
            xanchor="left",
            x=1.02,
            font=dict(size=12)
        ),
        height=400,
        margin=dict(t=80, b=20, l=20, r=120)  # Više mesta za legendu
    )
    
    return fig

def create_peak_hours_chart():
    """
    Kreira LINE CHART za peak hours (najviše upita po satima)
    OBJAŠNJENJE:
    - X-osa = sati u danu (0-23)
    - Y-osa = broj upita u tom satu
    - Pokazuje kada korisnici NAJVIŠE koriste sistem
    """
    data = get_queries_by_time()
    
    if not data:
        return None
    
    # Punjenje 0 za sate koji nemaju upite (da bi grafik bio kontinualan)
    hours_dict = {item['hour']: item['count'] for item in data}
    hours = list(range(24))  # 0-23
    counts = [hours_dict.get(h, 0) for h in hours]  # Ako nema podataka, stavi 0
    
    # Kreiramo line chart sa area fill
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=hours,
        y=counts,
        mode='lines+markers',
        fill='tozeroy',  # Popuni oblast ispod linije
        line=dict(color='#667eea', width=3),
        marker=dict(size=8, color='#764ba2'),
        hovertemplate='<b>%{x}:00h</b><br>Upita: %{y}<extra></extra>'
    ))
    
    fig.update_layout(
        title={
            'text': '⏰ Peak Hours - Aktivnost korisnika',
            'x': 0.5,
            'xanchor': 'center',
            'font': {'size': 20, 'color': '#667eea'}
        },
        xaxis_title='Sat dana',
        yaxis_title='Broj upita',
        xaxis=dict(
            tickmode='linear',
            tick0=0,
            dtick=2,  # Prikaži svaki drugi sat (0, 2, 4, ...)
            ticksuffix='h'
        ),
        height=400,
        margin=dict(t=80, b=50, l=50, r=20),
        hovermode='x unified'
    )
    
    return fig

def get_analytics_summary():
    """
    Vraća summarized statistiku za metrics kartice
    OBJAŠNJENJE: Ove brojke će biti prikazane kao "metric cards" u Streamlitu
    """
    return get_total_stats()

import streamlit as st
import math
import ssl
import json
import http.client
import urllib.parse
import urllib.request
import pandas as pd
from datetime import datetime
import folium
from streamlit_folium import st_folium
from streamlit_js_eval import get_geolocation

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Gasolineras Pro", page_icon="⛽", layout="centered")

# --- BLOQUE DE ESTILO CSS PARA COMPACTAR ---
st.markdown("""
    <style>
    /* Ajuste para que el título no se corte arriba */
    .block-container { 
        padding-top: 3.5rem !important; /* Aumentamos el margen superior */
        padding-bottom: 0rem; 
    }
    
    /* Evitar que el icono del título se desplace */
    h1 {
        padding-top: 0.5rem;
        margin-top: 0rem;
    }

    /* Reduce el espacio entre elementos de Streamlit */
    .stVerticalBlock { gap: 0.4rem; }
    
    /* Reduce el espacio específico de las alertas/info */
    .stAlert { margin-bottom: -10px; padding: 0.5rem; }
    
    /* Estilo para el texto de coordenadas */
    .coord-text { font-size: 0.8rem; color: #666; margin-top: -10px; margin-bottom: 5px; }
    
    /* Ocultar el menú superior de Streamlit para ganar más espacio (opcional) */
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

# 2. INICIALIZACIÓN DE MEMORIA
if 'lat' not in st.session_state: st.session_state.lat = None
if 'lon' not in st.session_state: st.session_state.lon = None
if 'resultados_busqueda' not in st.session_state: st.session_state.resultados_busqueda = None

# 3. FUNCIONES LÓGICAS (Sin cambios)
def get_json_ministerio(path: str) -> dict:
    host = "sedeaplicaciones.minetur.gob.es"
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    ctx.set_ciphers("DEFAULT:@SECLEVEL=0")
    conn = http.client.HTTPSConnection(host, context=ctx, timeout=40)
    conn.request("GET", path, headers={"User-Agent": "Mozilla/5.0"})
    resp = conn.getresponse()
    raw = resp.read()
    conn.close()
    return json.loads(raw.decode("utf-8"))

def geocodificar(direccion: str) -> tuple[float, float]:
    try:
        params = urllib.parse.urlencode({"q": direccion, "limit": 1})
        url = f"https://photon.komoot.io/api/?{params}"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data["features"]:
                lon, lat = data["features"][0]["geometry"]["coordinates"]
                return lat, lon
    except: pass
    return None

def distancia_km(lat1, lon1, lat2, lon2) -> float:
    R = 6371
    dlat, dlon = math.radians(lat2-lat1), math.radians(lon2-lon1)
    a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
    return R * 2 * math.asin(math.sqrt(a))

# 4. INTERFAZ DE USUARIO
st.title("⛽ Gasolineras")

modo_ubicacion = st.radio("Buscar por:", ["Dirección", "GPS Real"], horizontal=True)

if modo_ubicacion == "Dirección":
    direccion_input = st.text_input("📍 Ubicación:", value="Avenida Doctor Fedriani 47, Sevilla")
    if st.button("📍 Fijar"):
        coords = geocodificar(direccion_input)
        if coords:
            st.session_state.lat, st.session_state.lon = coords
            st.success("✅ Fijada")
else:
    # Bloque GPS más compacto
    loc = get_geolocation()
    if loc:
        st.session_state.lat = loc['coords']['latitude']
        st.session_state.lon = loc['coords']['longitude']
        st.success("📍 GPS Conectado")
    else:
        st.info("⌛ Obteniendo posición...")
    
    if st.button("🔄 Actualizar GPS"):
        st.rerun()

# Coordenadas con margen negativo vía HTML para que pegue a lo de arriba
if st.session_state.lat:
    st.markdown(f'<p class="coord-text">Coords: {round(st.session_state.lat,4)}, {round(st.session_state.lon,4)}</p>', unsafe_allow_html=True)

# Parámetros en columnas para ahorrar espacio vertical
c1, c2 = st.columns([2, 1])
with c1:
    combustible_opcion = st.selectbox("Combustible:", ["Precio Gasoleo A", "Precio Gasolina 95 E5"], 
                                    format_func=lambda x: "Diésel" if "Gasoleo" in x else "Gasolina 95")
with c2:
    radio_input = st.number_input("Radio (km):", 1, 50, 5)

# 5. BOTÓN DE BÚSQUEDA
if st.button("🚀 BUSCAR AHORA", use_container_width=True):
    if st.session_state.lat and st.session_state.lon:
        with st.spinner("Buscando..."):
            try:
                data = get_json_ministerio("/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/")
                gasolineras = data.get("ListaEESSPrecio", [])
                resultados = []
                for g in gasolineras:
                    try:
                        g_lat = float(g["Latitud"].replace(",", "."))
                        g_lon = float(g["Longitud (WGS84)"].replace(",", "."))
                        dist = distancia_km(st.session_state.lat, st.session_state.lon, g_lat, g_lon)
                        if dist <= radio_input:
                            precio_str = g.get(combustible_opcion, "").replace(",", ".")
                            if precio_str:
                                resultados.append({
                                    "Precio": float(precio_str),
                                    "Distancia": round(dist, 2),
                                    "Rótulo": g.get("Rótulo"),
                                    "Dirección": g.get("Dirección"),
                                    "lat": g_lat, "lon": g_lon
                                })
                    except: continue

                if resultados:
                    df = pd.DataFrame(resultados).sort_values("Precio").head(15).reset_index(drop=True)
                    df['Ranking'] = df.index + 1
                    df['Maps'] = df.apply(lambda r: f"https://www.google.com/maps/dir/?api=1&destination={r['lat']},{r['lon']}", axis=1)
                    st.session_state.resultados_busqueda = df
                else:
                    st.session_state.resultados_busqueda = None
                    st.warning("Sin resultados.")
            except Exception as e:
                st.error(f"Error: {e}")

# 6. RESULTADOS
if st.session_state.resultados_busqueda is not None:
    df = st.session_state.resultados_busqueda
    st.subheader("📋 Top 15 Económicas")
    st.dataframe(
        df[["Ranking", "Precio", "Distancia", "Rótulo", "Maps"]],
        column_config={"Maps": st.column_config.LinkColumn("📍 Ir")},
        use_container_width=True, hide_index=True
    )

    st.subheader("📍 Mapa")
    m = folium.Map(location=[st.session_state.lat, st.session_state.lon], zoom_start=13)
    folium.Marker([st.session_state.lat, st.session_state.lon], icon=folium.Icon(color='red')).add_to(m)
    for i, row in df.iterrows():
        folium.Marker(location=[row['lat'], row['lon']],
            icon=folium.DivIcon(html=f'<div style="font-family: Arial; color: white; background-color: #007bff; border-radius: 50%; width: 20px; height: 20px; display: flex; align-items: center; justify-content: center; font-size: 10px; border: 1px solid white;">{row["Ranking"]}</div>')
        ).add_to(m)
    st_folium(m, width=700, height=350)
    
    st.subheader("📊 Comparativa")
    df['Etiqueta'] = df['Ranking'].astype(str) + ". " + df['Rótulo']
    st.bar_chart(df, x="Etiqueta", y="Precio")




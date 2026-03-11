import streamlit as st
import math
import ssl
import json
import http.client
import urllib.parse
import urllib.request
import pandas as pd
from datetime import datetime

# Configuración de página para móvil
st.set_page_config(page_title="Gasolineras Baratas", page_icon="⛽", layout="centered")

# --- FUNCIONES DE LÓGICA (Tus funciones originales adaptadas) ---

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

# --- INTERFAZ DE USUARIO CON STREAMLIT ---

st.title("🔍 Buscador de Gasolineras")
st.markdown("Consulta precios oficiales del Ministerio en tiempo real.")

# Formulario de búsqueda
with st.form("buscador"):
    direccion_input = st.text_input("📍 Ubicación:", value="Avenida Doctor Fedriani 47, Sevilla")
    radio_input = st.slider("📏 Radio de búsqueda (km):", min_value=1, max_value=20, value=5)
    combustible_opcion = st.selectbox("⛽ Combustible:", 
                                     ["Precio Gasoleo A", "Precio Gasolina 95 E5"],
                                     format_func=lambda x: "Diésel" if "Gasoleo" in x else "Gasolina 95")
    boton_buscar = st.form_submit_button("Buscar las más baratas")

if boton_buscar:
    with st.spinner("Geocodificando y descargando precios..."):
        coords = geocodificar(direccion_input)
        
        if not coords:
            st.error("No se pudo encontrar la dirección. Intenta ser más específico.")
        else:
            lat_usr, lon_usr = coords
            
            try:
                # Descarga de datos
                data = get_json_ministerio("/ServiciosRESTCarburantes/PreciosCarburantes/EstacionesTerrestres/")
                gasolineras = data.get("ListaEESSPrecio", [])
                
                # Filtrado y cálculo
                resultados = []
                for g in gasolineras:
                    try:
                        g_lat = float(g["Latitud"].replace(",", "."))
                        g_lon = float(g["Longitud (WGS84)"].replace(",", "."))
                        dist = distancia_km(lat_usr, lon_usr, g_lat, g_lon)
                        
                        if dist <= radio_input:
                            precio_str = g.get(combustible_opcion, "").replace(",", ".")
                            if precio_str:
                                resultados.append({
                                    "Precio": float(precio_str),
                                    "Distancia (km)": round(dist, 2),
                                    "Rótulo": g.get("Rótulo"),
                                    "Municipio": g.get("Municipio"),
                                    "Dirección": g.get("Dirección")
                                })
                    except: continue

                if not resultados:
                    st.warning("No se encontraron gasolineras en ese radio.")
                else:
                    # Crear DataFrame para mostrar tabla
                    df = pd.DataFrame(resultados).sort_values("Precio").head(15)
                    
                    # Mostrar métricas rápidas
                    col1, col2 = st.columns(2)
                    col1.metric("Más barata", f"{df['Precio'].min()} €/L")
                    col2.metric("Media zona", f"{round(df['Precio'].mean(), 3)} €/L")
                    
                    # Mostrar Tabla
                    st.success(f"Encontradas {len(df)} gasolineras baratas:")
                    st.dataframe(df, use_container_width=True)
                    
                    # Gráfica rápida
                    st.subheader("Variación de precio en el Top 15")
                    st.bar_chart(df, x="Rótulo", y="Precio")

            except Exception as e:
                st.error(f"Error al conectar con el Ministerio: {e}")

st.divider()
st.caption(f"Datos actualizados: {datetime.now().strftime('%d/%m/%Y %H:%M')}")

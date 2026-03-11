import streamlit as st  # IMPORTANTE: Siempre la primera línea
import math
import ssl
import json
import http.client
import urllib.parse
import urllib.request
import pandas as pd
from datetime import datetime

# 1. CONFIGURACIÓN DE LA PÁGINA
st.set_page_config(page_title="Gasolineras Pro", page_icon="⛽", layout="centered")

# 2. INICIALIZACIÓN DE MEMORIA (Session State)
# Esto evita que la ubicación se borre al pulsar el botón de buscar
if 'lat' not in st.session_state:
    st.session_state.lat = None
if 'lon' not in st.session_state:
    st.session_state.lon = None

# 3. FUNCIONES LÓGICAS
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
st.title("⛽ Buscador de Gasolineras Pro")
st.markdown("Precios oficiales actualizados del Ministerio.")

# Selector de ubicación
modo_ubicacion = st.radio("Selecciona cómo buscar:", ["Escribir dirección", "Manual / GPS"])

if modo_ubicacion == "Escribir dirección":
    direccion_input = st.text_input("📍 Ubicación:", value="Avenida Doctor Fedriani 47, Sevilla")
    if st.button("📍 Fijar Dirección"):
        coords = geocodificar(direccion_input)
        if coords:
            st.session_state.lat, st.session_state.lon = coords
            st.success(f"✅ Ubicación fijada: {st.session_state.lat}, {st.session_state.lon}")
        else:
            st.error("No se encontró la dirección.")
else:
    st.info("Introduce coordenadas manualmente:")
    c1, c2 = st.columns(2)
    st.session_state.lat = c1.number_input("Latitud:", value=st.session_state.lat if st.session_state.lat else 37.413, format="%.5f")
    st.session_state.lon = c2.number_input("Longitud:", value=st.session_state.lon if st.session_state.lon else -5.978, format="%.5f")

st.divider()

# Parámetros de búsqueda
radio_input = st.slider("📏 Radio de búsqueda (km):", 1, 30, 5)
combustible_opcion = st.selectbox("⛽ Combustible:", 
                                 ["Precio Gasoleo A", "Precio Gasolina 95 E5"],
                                 format_func=lambda x: "Diésel" if "Gasoleo" in x else "Gasolina 95")


# 5. EJECUCIÓN DE BÚSQUEDA
if st.button("🚀 BUSCAR LAS MÁS BARATAS"):
    if st.session_state.lat and st.session_state.lon:
        with st.spinner("Consultando precios en tiempo real..."):
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
                                    "lat": g_lat,
                                    "lon": g_lon,
                                    "Maps": f"https://www.google.com/maps/dir/?api=1&destination={g_lat},{g_lon}"
                                })
                    except: continue

                if resultados:
                    df = pd.DataFrame(resultados).sort_values("Precio").head(15)
                    df['Etiqueta'] = df['Rótulo'] + " (" + df['Dirección'].str[:10] + ")"

                    # 1. MÉTRICAS (Arriba del todo para resumen rápido)
                    m1, m2 = st.columns(2)
                    m1.metric("Precio Mínimo", f"{df['Precio'].min()} €")
                    m2.metric("Ahorro medio", f"{round(df['Precio'].mean() - df['Precio'].min(), 3)} €")

                    st.divider()

                    # 2. LISTADO DETALLADO (Lo primero que pediste)
                    st.subheader("📋 Listado de las 15 más baratas")
                    st.dataframe(
                        df[["Precio", "Distancia", "Rótulo", "Dirección", "Maps"]],
                        column_config={"Maps": st.column_config.LinkColumn("📍 Ir en Maps")},
                        use_container_width=True,
                        hide_index=True
                    )

                    # 3. MAPA (Debajo del listado)
                    st.subheader("📍 Ubicación en el mapa")
                    st.map(df[['lat', 'lon']])

                    # 4. GRÁFICA (Al final)
                    st.subheader("📊 Comparativa visual de precios")
                    st.bar_chart(df, x="Etiqueta", y="Precio")
                    
                else:
                    st.warning("No hay gasolineras en ese radio. Prueba a aumentarlo.")
            except Exception as e:
                st.error(f"Error en la conexión con el Ministerio: {e}")
    else:
        st.error("⚠️ Primero debes fijar una ubicación arriba.")

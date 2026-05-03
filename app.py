import streamlit as st
import json
import requests
import base64
from bs4 import BeautifulSoup
from datetime import datetime, date

st.set_page_config(page_title="Buscador Tee Times", layout="wide")
st.image("header.jpg", use_container_width=True)

# =========================
# FUNCIONES
# =========================

def convertir_hora(hora_texto):
    return datetime.strptime(hora_texto, "%H:%M").time()

def obtener_valor_hidden(soup, id_campo):
    campo = soup.find("input", {"id": id_campo})
    return campo.get("value") if campo else None

def recorrido_cumple_filtros(recorrido, filtro_hoyos, filtro_tipo):
    if filtro_hoyos == "18" and not recorrido.get("18hoyos", False):
        return False
    if filtro_hoyos == "9" and not recorrido.get("9Hoyos", False):
        return False
    if filtro_tipo == "corto" and not recorrido.get("CampoCorto", False):
        return False
    if filtro_tipo == "largo" and recorrido.get("CampoCorto", False):
        return False
    return True

def formatear_nombre_recorrido(recorrido):
    nombre = recorrido.get("nombre", "Recorrido")
    if recorrido.get("CampoCorto", False):
        nombre += " (Pitch & Putt)"
    return nombre

def consultar_recorrido(session, campo, recorrido, token, id_inicio, api, culture,
                        fecha, hora_inicio, hora_fin, jugadores):

    payload = {
        "culture": culture,
        "fecha": fecha,
        "horaFin": hora_fin,
        "horaInicio": hora_inicio,
        "idInicioSesion": id_inicio,
        "idRecorrido": str(recorrido["id_recorrido"]),
        "idTarifaTipoUso": 1,
        "idVendedor": str(campo["id_vendedor"]),
        "idVendedorProveedor": str(campo["id_vendedor_proveedor"]),
        "idVendedorTourOperador": "-1",
        "jugadores": "-1",
        "pageNum": -1,
        "pageSize": 50,
        "precioFin": "2000",
        "precioInicio": "1",
        "promoCode": "",
        "Token": token
    }

    headers = {
        "Content-Type": "application/json",
        "Origin": "https://open.teeone.golf",
        "Referer": "https://open.teeone.golf/",
        "User-Agent": "Mozilla/5.0"
    }

    try:
        r = session.post(
            api + "/Api/Disponibilidad/ObtenerDisponibilidadDia",
            json=payload,
            headers=headers
        )
        data = r.json()
    except:
        return []

    horas = data.get("horasDisponibles")
    if not horas:
        return []

    resultados = []

    for h in horas:
        hora = h.get("hora")
        jugadores_disp = h.get("jugadoresDisponibles", 0)

        if jugadores_disp < jugadores:
            continue

        tarifas = [
            {"nombre": t.get("nombre"), "precio": t.get("precio")}
            for t in h.get("tarifas", [])
        ]

        if tarifas:
            resultados.append({
                "campo": campo["nombre"],
                "recorrido": formatear_nombre_recorrido(recorrido),
                "hora": hora,
                "jugadores_disponibles": jugadores_disp,
                "tarifas": tarifas,
                "url_reserva": campo.get("url_reserva", "No disponible"),
                "email_reservas": campo.get("email_reservas", "No disponible"),
                "telefono_reserva": campo.get("telefono_reserva", "No disponible")
            })

    return resultados

def buscar_teetimes(fecha, hora_inicio, hora_fin, jugadores, filtro_hoyos, filtro_tipo):
    with open("campos_teeone.json", "r", encoding="utf-8") as f:
        campos = json.load(f)

    resultados = []

    for campo in campos:
        session = requests.Session()

        try:
            r = session.get(campo["url_reserva"])
            soup = BeautifulSoup(r.text, "html.parser")

            token = obtener_valor_hidden(soup, "HidTokenAPI")
            id_inicio = obtener_valor_hidden(soup, "HidInicioSesion")
            api = obtener_valor_hidden(soup, "HidAPIDominio")
            culture = obtener_valor_hidden(soup, "HidCultura")

            if not token:
                continue
        except:
            continue

        for recorrido in campo.get("Recorridos", []):
            if not recorrido_cumple_filtros(recorrido, filtro_hoyos, filtro_tipo):
                continue

            resultados.extend(
                consultar_recorrido(
                    session, campo, recorrido, token, id_inicio, api, culture,
                    fecha, hora_inicio, hora_fin, jugadores
                )
            )

    return sorted(resultados, key=lambda r: (r["campo"], convertir_hora(r["hora"])))

# =========================
# INTERFAZ
# =========================

st.markdown("<div class='subtitle'>Busca salidas disponibles en campos de golf cercanos.</div>", unsafe_allow_html=True)

st.markdown("""
<style>
.main-title {
    font-size: 34px;
    font-weight: 800;
    margin-bottom: 4px;
}

.subtitle {
    font-size: 17px;
    color: #666;
    margin-bottom: 24px;
}

.search-panel {
    border: 1px solid #e5e5e5;
    border-radius: 18px;
    padding: 20px;
    margin-bottom: 24px;
    background-color: #fafafa;
    box-shadow: 0 2px 8px rgba(0,0,0,0.04);
}

.result-summary {
    border-radius: 14px;
    padding: 12px 16px;
    margin: 16px 0 22px 0;
    background-color: #eaf7ef;
    color: #145c32;
    font-weight: 700;
}

.result-card {
    border: 1px solid #e1e1e1;
    border-radius: 18px;
    padding: 16px;
    margin-bottom: 18px;
    background-color: #ffffff;
    box-shadow: 0 3px 10px rgba(0,0,0,0.07);
    min-height: 285px;
}

.result-title {
    font-size: 19px;
    font-weight: 800;
    margin-bottom: 10px;
    color: #222;
}

.result-meta {
    font-size: 17px;
    margin-bottom: 10px;
    color: #333;
}

.result-recorrido {
    font-size: 15px;
    margin-bottom: 12px;
    color: #555;
    min-height: 38px;
}

.tarifas-title {
    font-size: 15px;
    font-weight: 700;
    margin-bottom: 6px;
}

.tarifa {
    font-size: 14px;
    margin-bottom: 5px;
    color: #333;
}

hr.card-separator {
    border: none;
    border-top: 1px solid #eee;
    margin: 12px 0;
}
</style>
""", unsafe_allow_html=True)

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SLOT_MINUTES = 10
TZ = ZoneInfo("Europe/Madrid")


st.markdown("""
<style>
div.stButton > button[kind="primary"] {
    background-color: #243447;
    border-color: #243447;
    color: white;
}

div.stButton > button[kind="secondary"] {
    background-color: #f0f2f6;
    border-color: #c9ced6;
    color: #243447;
}
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
/* Slider */
.stSlider [data-baseweb="slider"] div[role="slider"] {
    background-color: #243447 !important;
    border-color: #243447 !important;
}

.stSlider [data-baseweb="slider"] > div > div {
    background-color: #243447 !important;
}

.stSlider [data-baseweb="slider"] span {
    color: #243447 !important;
}
</style>
""", unsafe_allow_html=True)

def redondear_hora_actual():
    ahora = datetime.now(TZ)

    minutos_redondeados = ((ahora.minute + SLOT_MINUTES - 1) // SLOT_MINUTES) * SLOT_MINUTES

    hora_redondeada = ahora.replace(minute=0, second=0, microsecond=0) + timedelta(minutes=minutos_redondeados)

    hora_min = ahora.replace(hour=7, minute=0, second=0, microsecond=0)
    hora_max = ahora.replace(hour=20, minute=0, second=0, microsecond=0)

    if hora_redondeada < hora_min:
        hora_redondeada = hora_min

    if hora_redondeada > hora_max:
        hora_redondeada = hora_max

    return hora_redondeada.time()


def toggle_multi_obligatorio(clave, valor):
    seleccion = st.session_state[clave]

    if valor in seleccion:
        if len(seleccion) > 1:
            seleccion.remove(valor)
    else:
        seleccion.append(valor)

    st.session_state[clave] = seleccion


if "jugadores" not in st.session_state:
    st.session_state.jugadores = 4

if "hoyos_seleccionados" not in st.session_state:
    st.session_state.hoyos_seleccionados = ["18", "9"]

if "tipo_seleccionado" not in st.session_state:
    st.session_state.tipo_seleccionado = ["largo", "corto"]


hora_inicio_default = redondear_hora_actual()
hora_fin_default_dt = datetime.combine(date.today(), hora_inicio_default) + timedelta(hours=1)
hora_fin_default = min(hora_fin_default_dt.time(), time(20, 0))

with st.container(border=True):
    st.markdown("### 🔎 Criterios de búsqueda")

    col1, col2 = st.columns([1, 2])

    with col1:
        fecha = st.date_input(
            "Fecha",
            value=date.today(),
            min_value=date.today(),
            format="DD/MM/YYYY"
        )

    with col2:
        hora_inicio, hora_fin = st.slider(
            "Franja horaria",
            min_value=time(7, 0),
            max_value=time(20, 0),
            value=(hora_inicio_default, hora_fin_default),
            step=timedelta(minutes=SLOT_MINUTES),
            format="HH:mm"
        )

    col3, col4, col5 = st.columns([1.6, 1, 1])

    with col3:
        st.markdown("**Jugadores**")
        cols_jugadores = st.columns(4)
    
        for i, num in enumerate([1, 2, 3, 4]):
            with cols_jugadores[i]:
                tipo_boton = "primary" if st.session_state.jugadores == num else "secondary"
                if st.button(f"🏌️ x {num}", type=tipo_boton, key=f"jug_{num}"):
                    st.session_state.jugadores = num
    
    with col4:
    st.markdown("**Hoyos**")
    btn18, btn9, espacio = st.columns([1, 1, 2.5])

        with btn18:
            if st.button(
                "18",
                type="primary" if "18" in st.session_state.hoyos_seleccionados else "secondary",
                key="hoyos_18"
            ):
                toggle_multi_obligatorio("hoyos_seleccionados", "18")
    
        with btn9:
            if st.button(
                "9",
                type="primary" if "9" in st.session_state.hoyos_seleccionados else "secondary",
                key="hoyos_9"
            ):
                toggle_multi_obligatorio("hoyos_seleccionados", "9")
    
    with col5:
    st.markdown("**Tipo campo**")
    btn_largo, btn_corto, espacio = st.columns([1, 1, 2.5])

        with btn_largo:
            if st.button(
                "Largo",
                type="primary" if "largo" in st.session_state.tipo_seleccionado else "secondary",
                key="tipo_largo"
            ):
                toggle_multi_obligatorio("tipo_seleccionado", "largo")
    
        with btn_corto:
            if st.button(
                "Corto",
                type="primary" if "corto" in st.session_state.tipo_seleccionado else "secondary",
                key="tipo_corto"
            ):
                toggle_multi_obligatorio("tipo_seleccionado", "corto")

    hora_inicio_txt = hora_inicio.strftime("%H:%M")
    hora_fin_txt = hora_fin.strftime("%H:%M")

if st.button("Buscar"):

    try:
        fecha_api = fecha.strftime("%Y/%m/%d")
        hora_inicio_api = datetime.strptime(hora_inicio_txt, "%H:%M").strftime("%H:%M")
        hora_fin_api = datetime.strptime(hora_fin_txt, "%H:%M").strftime("%H:%M")
    except ValueError:
        st.error("Revisa el formato de las horas. Deben estar en formato HH:MM.")
        st.stop()

    if hora_fin_api <= hora_inicio_api:
        st.error("La hora fin debe ser posterior a la hora inicio.")
        st.stop()

    resultados = buscar_teetimes(
        fecha_api,
        hora_inicio_api,
        hora_fin_api,
        jugadores,
        filtro_hoyos,
        filtro_tipo
    )

    if not resultados:
        st.warning("No se encontraron salidas disponibles con esos criterios.")
    else:
        st.markdown(
        f"<div class='result-summary'>Se encontraron {len(resultados)} salidas disponibles.</div>",
        unsafe_allow_html=True
        )

        for i in range(0, len(resultados), 4):
            columnas = st.columns(4)

            for col, r in zip(columnas, resultados[i:i+4]):
                tarifas_html = ""

                for t in r["tarifas"]:
                    tarifas_html += f"<div class='tarifa'>• {t['nombre']}: <b>{t['precio']} €</b></div>"

                with col:
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-title">{r['campo']}</div>
                        <div class="result-meta">🕒 <b>{r['hora']}</b> · 🏌️ x {r['jugadores_disponibles']}</div>
                        <div class="result-recorrido">{r['recorrido']}</div>
                        <hr class="card-separator">
                        <div class="tarifas-title">Tarifas</div>
                        {tarifas_html}
                    </div>
                    """, unsafe_allow_html=True)
                
                    with st.expander("Info Reservas"):
                        st.write(f"**Web reservas:** {r.get('url_reserva', 'No disponible')}")
                        st.write(f"**Email:** {r.get('email_reservas', 'No disponible')}")
                        st.write(f"**Teléfono:** {r.get('telefono_reserva', 'No disponible')}")

st.markdown("------")

st.markdown(
    "<p style='text-align:center; font-size:12px; color:gray;'>Versión BETA</p>",
    unsafe_allow_html=True
)

col1, col2, col3 = st.columns([1, 2, 1])

with col2:
    st.markdown(
        "<div style='text-align:center;'>"
        "<img src='data:image/png;base64,{}' width='400'>"
        "</div>".format(
            base64.b64encode(open("powered.png", "rb").read()).decode()
        ),
        unsafe_allow_html=True
    )

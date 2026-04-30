import streamlit as st
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

st.set_page_config(page_title="Buscador Tee Times", layout="wide")

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
        r = session.post(api + "/Api/Disponibilidad/ObtenerDisponibilidadDia",
                         json=payload, headers=headers)
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
                "url_reserva": campo["url_reserva"]
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

st.title("🏌️ Open Tee Times")
st.write("Busca salidas disponibles en campos de golf cercanos.")

st.markdown("""
<style>
.result-card {
    border: 1px solid #ddd;
    border-radius: 14px;
    padding: 18px;
    margin-bottom: 16px;
    background-color: #ffffff;
    box-shadow: 0 2px 6px rgba(0,0,0,0.06);
}
.result-title {
    font-size: 22px;
    font-weight: 700;
    margin-bottom: 6px;
}
.result-meta {
    font-size: 18px;
    margin-bottom: 10px;
}
.tarifa {
    margin-left: 12px;
    font-size: 16px;
}
.reserva {
    display: inline-block;
    margin-top: 12px;
    padding: 8px 14px;
    border-radius: 8px;
    background-color: #1f7a4d;
    color: white !important;
    text-decoration: none;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)

col1, col2, col3 = st.columns(3)

with col1:
    fecha_txt = st.text_input("Fecha", value="29/04/2026", help="Formato DD/MM/AAAA")

with col2:
    hora_inicio_txt = st.text_input("Hora inicio", value="14:40", help="Formato HH:MM")

with col3:
    hora_fin_txt = st.text_input("Hora fin", value="15:00", help="Formato HH:MM")

col4, col5, col6 = st.columns(3)

with col4:
    jugadores = st.number_input("Jugadores", min_value=1, max_value=4, value=4)

with col5:
    filtro_hoyos = st.selectbox("Hoyos", ["todos", "18", "9"])

with col6:
    filtro_tipo = st.selectbox("Tipo campo", ["todos", "largo", "corto"])

if st.button("Buscar"):

    try:
        fecha_api = datetime.strptime(fecha_txt, "%d/%m/%Y").strftime("%Y/%m/%d")
        hora_inicio_api = datetime.strptime(hora_inicio_txt, "%H:%M").strftime("%H:%M")
        hora_fin_api = datetime.strptime(hora_fin_txt, "%H:%M").strftime("%H:%M")
    except ValueError:
        st.error("Revisa el formato: fecha DD/MM/AAAA y horas HH:MM.")
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
        st.success(f"Se encontraron {len(resultados)} salidas disponibles.")

        for r in resultados:
            tarifas_html = ""

            for t in r["tarifas"]:
                tarifas_html += f"<div class='tarifa'>• {t['nombre']}: <b>{t['precio']} €</b></div>"

            st.markdown(f"""
            <div class="result-card">
                <div class="result-title">{r['campo']}</div>
                <div class="result-meta">
                    ⏱️ <b>{r['hora']}</b> · {r['recorrido']} · 🏌️ x {r['jugadores_disponibles']}
                </div>
                <div><b>Tarifas:</b></div>
                {tarifas_html}
                <a class="reserva" href="{r['url_reserva']}" target="_blank">Reservar</a>
            </div>
            """, unsafe_allow_html=True)

import streamlit as st
import json
import requests
import base64
import math
from bs4 import BeautifulSoup
from datetime import datetime, date

st.set_page_config(
    page_title="TeeRadar",
    page_icon="favicon.png",
    layout="wide"
)

st.image("header.jpg", use_container_width=True)

# =========================
# CONFIGURACIÓN
# =========================

NOMBRE_FICHERO_CAMPOS = "CamposTeeRadar.json"

# =========================
# MODO DEBUG
# =========================

params = st.query_params
modo_debug = params.get("debug") == "1"

if "debug_payloads" not in st.session_state:
    st.session_state.debug_payloads = []

if "debug_responses" not in st.session_state:
    st.session_state.debug_responses = []

def registrar_debug(tipo, campo, recorrido, contenido):
    if not modo_debug:
        return

    entrada = {
        "campo": campo.get("nombre", "Campo sin nombre") if campo else "Campo sin nombre",
        "recorrido": recorrido.get("nombre", "Recorrido sin nombre") if recorrido else "Recorrido sin nombre",
        "contenido": contenido
    }

    if tipo == "payload":
        st.session_state.debug_payloads.append(entrada)
    elif tipo == "response":
        st.session_state.debug_responses.append(entrada)

def es_herreria(campo):
    return "herrer" in str(campo.get("nombre", "")).lower()

def debug_herreria(etapa, datos=None):
    if not modo_debug:
        return

    if datos is None:
        st.write(f"🧪 DEBUG HERRERÍA - {etapa}")
    else:
        st.write(f"🧪 DEBUG HERRERÍA - {etapa}", datos)

def formatear_debug(lista):
    bloques = []

    for i, entrada in enumerate(lista, start=1):
        bloques.append(
            f"===== {i}. {entrada['campo']} | {entrada['recorrido']} =====\n"
            + json.dumps(entrada["contenido"], ensure_ascii=False, indent=2)
        )

    return "\n\n".join(bloques)

def pintar_caja_debug(titulo, lista):
    st.text_area(
        titulo,
        value=formatear_debug(lista),
        height=260,
        disabled=True
    )

# =========================
# FUNCIONES
# =========================

def convertir_hora(hora_texto):
    return datetime.strptime(hora_texto, "%H:%M").time()

def obtener_valor_hidden(soup, id_campo):
    campo = soup.find("input", {"id": id_campo})
    return campo.get("value") if campo else None

def es_campo_activo(campo):
    activo = campo.get("activo", True)
    if isinstance(activo, bool):
        return activo
    if isinstance(activo, str):
        return activo.strip().lower() not in ("false", "0", "no", "n")
    return bool(activo)

def cargar_campos(solo_activos=True):
    try:
        with open(NOMBRE_FICHERO_CAMPOS, "r", encoding="utf-8") as f:
            campos = json.load(f)
    except FileNotFoundError:
        st.error(f"No se encuentra el archivo {NOMBRE_FICHERO_CAMPOS}.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"El archivo {NOMBRE_FICHERO_CAMPOS} no tiene formato JSON válido: {e}")
        st.stop()

    if solo_activos:
        campos = [campo for campo in campos if es_campo_activo(campo)]

    return campos

def cargar_localidades():
    try:
        with open("LocalidadesEspaña.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("No se encuentra el archivo LocalidadesEspaña.json.")
        st.stop()
    except json.JSONDecodeError as e:
        st.error(f"El archivo LocalidadesEspaña.json no tiene formato JSON válido: {e}")
        st.stop()

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

def construir_resultado(campo, recorrido, hora, jugadores_disp, tarifas):
    return {
        "campo": campo["nombre"],
        "recorrido": formatear_nombre_recorrido(recorrido),
        "hora": hora,
        "jugadores_disponibles": jugadores_disp,
        "tarifas": tarifas,
        "url_reserva": campo.get("url_reserva", "No disponible"),
        "email_reservas": campo.get("email_reservas", "No disponible"),
        "telefono_reserva": campo.get("telefono_reserva", "No disponible"),
        "distancia_km": campo.get("distancia_km")
    }

def calcular_distancia_km(lat1, lon1, lat2, lon2):
    import math

    R = 6371

    lat1 = float(lat1)
    lon1 = float(lon1)
    lat2 = float(lat2)
    lon2 = float(lon2)

    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )

    a = min(1, max(0, a))

    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def consultar_recorrido_teeone_v1(session, campo, recorrido, token, id_inicio, api, culture,
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
        registrar_debug("payload", campo, recorrido, payload)

        r = session.post(
            api + "/Api/Disponibilidad/ObtenerDisponibilidadDia",
            json=payload,
            headers=headers,
            timeout=20
        )
        data = r.json()

        registrar_debug("response", campo, recorrido, data)

    except Exception as e:
        registrar_debug("response", campo, recorrido, {"error": str(e)})
        return []

    horas = data.get("horasDisponibles")
    if not horas:
        return []

    resultados = []

    for h in horas:
        hora = h.get("hora")
        jugadores_disp = h.get("jugadoresDisponibles", 0)

        if not hora or jugadores_disp < jugadores:
            continue

        tarifas = [
            {"nombre": t.get("nombre"), "precio": t.get("precio")}
            for t in h.get("tarifas", [])
        ]

        if tarifas:
            resultados.append(
                construir_resultado(campo, recorrido, hora, jugadores_disp, tarifas)
            )

    return resultados

def consultar_campo_teeone_v1(campo, fecha, hora_inicio, hora_fin, jugadores, filtro_hoyos, filtro_tipo):
    resultados = []
    session = requests.Session()

    try:
        r = session.get(campo["url_reserva"], timeout=20)
        soup = BeautifulSoup(r.text, "html.parser")

        token = obtener_valor_hidden(soup, "HidTokenAPI")
        id_inicio = obtener_valor_hidden(soup, "HidInicioSesion")
        api = obtener_valor_hidden(soup, "HidAPIDominio")
        culture = obtener_valor_hidden(soup, "HidCultura")

        if not token or not api:
            return []
    except Exception:
        return []

    for recorrido in campo.get("Recorridos", []):
        if not recorrido.get("id_recorrido"):
            continue
        if not recorrido_cumple_filtros(recorrido, filtro_hoyos, filtro_tipo):
            continue

        resultados.extend(
            consultar_recorrido_teeone_v1(
                session, campo, recorrido, token, id_inicio, api, culture,
                fecha, hora_inicio, hora_fin, jugadores
            )
        )

    return resultados

def extraer_lista_ofertas_v2(data):
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []

    for clave in (
        "ofertas", "Ofertas", "data", "Data", "items", "Items",
        "result", "Result", "results", "Results", "horasDisponibles"
    ):
        valor = data.get(clave)
        if isinstance(valor, list):
            return valor
        if isinstance(valor, dict):
            sublista = extraer_lista_ofertas_v2(valor)
            if sublista:
                return sublista

    return []

def normalizar_hora(hora):
    if not hora:
        return None
    hora = str(hora).strip()
    if "T" in hora:
        hora = hora.split("T")[-1]
    if len(hora) >= 5:
        return hora[:5]
    return None

def consultar_recorrido_teeone_v2(session, campo, recorrido, fecha, hora_inicio, hora_fin, jugadores):
    endpoint = campo.get("url_api")
    if not endpoint:
        return []

    payload = {
        "culture": "es-ES",
        "fecha": fecha,
        "horaInicio": hora_inicio,
        "horaFin": hora_fin,
        "hoyos": str(recorrido.get("id_hoyos")),
        "idAgente": str(campo.get("id_agente")),
        "idClub": str(campo.get("id_club")),
        "idRecorrido": str(recorrido.get("id_recorrido")),
        "jugadores": str(jugadores),
        "pageNum": 1,
        "pageSize": 10,
        "precioFin": "130",
        "precioInicio": "10"
    }

    headers = {
        "Content-Type": "application/json",
        "Origin": "https://centronacional.teeone.golf",
        "Referer": campo.get("url_reserva", ""),
        "User-Agent": "Mozilla/5.0"
    }

    try:
        registrar_debug("payload", campo, recorrido, payload)

        r = session.post(endpoint, json=payload, headers=headers, timeout=20)
        data = r.json()

        registrar_debug("response", campo, recorrido, data)

    except Exception as e:
        registrar_debug("response", campo, recorrido, {"error": str(e)})
        return []

    horas = data.get("horasDisponibles")
    if not horas:
        return []

    resultados = []

    for h in horas:
        hora = h.get("hora")
        jugadores_disp = h.get("jugadoresDisponibles", 0)

        if not hora or jugadores_disp < jugadores:
            continue

        tarifas = []

        for t in h.get("tarifas", []):
            precio = t.get("precio")

            if precio is None:
                continue

            tarifas.append({
                "nombre": t.get("nombre", "Tarifa"),
                "precio": precio
            })

        if tarifas:
            resultados.append(
                construir_resultado(campo, recorrido, hora, jugadores_disp, tarifas)
            )

    return resultados

def consultar_campo_teeone_v2(campo, fecha, hora_inicio, hora_fin, jugadores, filtro_hoyos, filtro_tipo):
    resultados = []
    session = requests.Session()

    try:
        session.get(campo.get("url_reserva", ""), timeout=20)
    except Exception:
        pass

    for recorrido in campo.get("Recorridos", []):
        if not recorrido.get("id_recorrido"):
            continue
        if not recorrido_cumple_filtros(recorrido, filtro_hoyos, filtro_tipo):
            continue

        resultados.extend(
            consultar_recorrido_teeone_v2(
                session, campo, recorrido,
                fecha, hora_inicio, hora_fin, jugadores
            )
        )

    return resultados

def tarifa_cumple_filtro_hoyos_golfmanager(tarifa, filtro_hoyos):
    """
    Golfmanager puede devolver varias tarifas para la misma hora:
    por ejemplo GF 9 hoyos y GF 18 hoyos.
    Si la respuesta trae tags como 9holes/18holes, los usamos para filtrar.
    Si no trae tags, no descartamos la tarifa.
    """
    if filtro_hoyos not in ("18", "9"):
        return True

    tags = tarifa.get("tags") or tarifa.get("apiTags") or []
    if not isinstance(tags, list):
        tags = []

    tags_normalizados = [str(tag).lower() for tag in tags]

    if "18holes" in tags_normalizados or "9holes" in tags_normalizados:
        if filtro_hoyos == "18":
            return "18holes" in tags_normalizados
        if filtro_hoyos == "9":
            return "9holes" in tags_normalizados

    nombre = str(tarifa.get("name") or tarifa.get("priceName") or "").lower()

    if "18" in nombre or "9" in nombre:
        if filtro_hoyos == "18":
            return "18" in nombre
        if filtro_hoyos == "9":
            return "9" in nombre

    return True

def consultar_campo_golfmanager(campo, fecha, hora_inicio, hora_fin, jugadores, filtro_hoyos, filtro_tipo):
    resultados = []
    endpoint = campo.get("url_api")

    if not endpoint:
        return []

    recorridos_validos = [
        recorrido
        for recorrido in campo.get("Recorridos", [])
        if recorrido_cumple_filtros(recorrido, filtro_hoyos, filtro_tipo)
    ]

    if modo_debug and es_herreria(campo):
        debug_herreria("GOLFMANAGER - RECORRIDOS TRAS FILTROS", {
            "filtro_hoyos": filtro_hoyos,
            "filtro_tipo": filtro_tipo,
            "recorridos_originales": campo.get("Recorridos", []),
            "recorridos_validos": recorridos_validos
        })

    if not recorridos_validos:
        if modo_debug and es_herreria(campo):
            debug_herreria("GOLFMANAGER - SIN RECORRIDOS VÁLIDOS, NO CREA PAYLOAD")
        return []

    fecha_golfmanager = str(fecha).replace("/", "-")

    headers = {
        "Accept": "*/*",
        "Referer": campo.get("url_reserva", ""),
        "User-Agent": "Mozilla/5.0",
        "clienturl": "/consumer/ebookings?i=1&resourcetype=1"
    }

    session = requests.Session()

    try:
        # Llamada previa para que Golfmanager pueda generar cookies de sesión si las necesita.
        if campo.get("url_reserva"):
            session.get(campo.get("url_reserva"), headers=headers, timeout=20)
    except Exception:
        # Si falla la llamada previa, no detenemos la búsqueda.
        pass

    for recorrido in recorridos_validos:
        id_resource_type = recorrido.get(
            "idResourceType",
            recorrido.get(
                "resourcetype",
                campo.get("idResourceType", campo.get("resourcetype", 1))
            )
        )

        id_resource = recorrido.get(
            "idResource",
            recorrido.get(
                "resource",
                campo.get("idResource", campo.get("resource"))
            )
        )

        params = {
            "idResourceType": id_resource_type,
            "start": f"{fecha_golfmanager}T{hora_inicio}:00",
            "cachebreaker": int(datetime.now().timestamp() * 1000)
        }

        if id_resource is not None:
            params["idResource"] = id_resource

        try:
            registrar_debug("payload", campo, recorrido, params)

            r = session.get(endpoint, params=params, headers=headers, timeout=20)
            data = r.json()

            registrar_debug("response", campo, recorrido, data)

        except Exception as e:
            registrar_debug("response", campo, recorrido, {"error": str(e)})
            continue

        availability = data.get("availability", [])

        if isinstance(availability, dict):
            availability = list(availability.values())

        if not isinstance(availability, list):
            registrar_debug("response", campo, recorrido, {
                "error": "availability no es una lista",
                "availability": availability
            })
            continue

        if not availability:
            continue

        for slot in availability:
            if not isinstance(slot, dict):
                registrar_debug("response", campo, recorrido, {
                    "aviso": "Elemento availability ignorado porque no es un diccionario",
                    "valor": slot
                })
                continue

            hora = normalizar_hora(slot.get("date") or slot.get("start"))
            jugadores_disp = slot.get("slots", 0)

            if not hora:
                continue

            try:
                jugadores_disp = int(jugadores_disp)
            except (TypeError, ValueError):
                jugadores_disp = 0

            if jugadores_disp < jugadores:
                continue

            if hora < hora_inicio or hora > hora_fin:
                continue

            tarifas = []

            tipos = slot.get("types", [])
            if not isinstance(tipos, list):
                tipos = []

            for tipo in tipos:
                if not isinstance(tipo, dict):
                    continue

                if tipo.get("onlyMembers", False):
                    continue

                if not tarifa_cumple_filtro_hoyos_golfmanager(tipo, filtro_hoyos):
                    continue

                precio = tipo.get("price")
                if precio is None:
                    continue

                tarifas.append({
                    "nombre": (tipo.get("name") or tipo.get("priceName") or "Tarifa").strip(),
                    "precio": precio
                })

            if tarifas:
                resultados.append(
                    construir_resultado(campo, recorrido, hora, jugadores_disp, tarifas)
                )

    return resultados

def consultar_campo_golfmanager_v2(campo, fecha, hora_inicio, hora_fin, jugadores, filtro_hoyos, filtro_tipo):
    resultados = []
    endpoint = campo.get("url_api")

    if not endpoint:
        return []

    recorridos_validos = [
        recorrido
        for recorrido in campo.get("Recorridos", [])
        if recorrido_cumple_filtros(recorrido, filtro_hoyos, filtro_tipo)
    ]

    if modo_debug and es_herreria(campo):
        debug_herreria("GMV2 - RECORRIDOS TRAS FILTROS", {
            "filtro_hoyos": filtro_hoyos,
            "filtro_tipo": filtro_tipo,
            "recorridos_originales": campo.get("Recorridos", []),
            "recorridos_validos": recorridos_validos
        })

    if not recorridos_validos:
        if modo_debug and es_herreria(campo):
            debug_herreria("GMV2 - SIN RECORRIDOS VÁLIDOS, NO CREA PAYLOAD")
        return []

    recorrido = recorridos_validos[0]

    fecha_golfmanager = str(fecha).replace("/", "-")

    params = {
        "date": f"{fecha_golfmanager}T{hora_inicio}",
        "area": campo.get("area", 100),
        "participants": jugadores
    }

    headers = {
        "Accept": "application/json",
        "User-Agent": "Mozilla/5.0",
        "Referer": campo.get("url_reserva", "")
    }

    session = requests.Session()

    try:
        registrar_debug("payload", campo, recorrido, params)

        r = session.get(endpoint, params=params, headers=headers, timeout=20)
        data = r.json()

        registrar_debug("response", campo, recorrido, data)

    except Exception as e:
        registrar_debug("response", campo, recorrido, {"error": str(e)})
        return []

    items = data.get("items", [])

    if not isinstance(items, list):
        registrar_debug("response", campo, recorrido, {
            "error": "items no es una lista",
            "items": items
        })
        return []

    resultados_agrupados = {}

    for item in items:
        if not isinstance(item, dict):
            continue

        hora = normalizar_hora(item.get("start"))
        jugadores_disp = item.get("slots", 0)

        if not hora:
            continue

        try:
            jugadores_disp = int(jugadores_disp)
        except (TypeError, ValueError):
            jugadores_disp = 0

        if jugadores_disp < jugadores:
            continue

        if hora < hora_inicio or hora > hora_fin:
            continue

        if not tarifa_cumple_filtro_hoyos_golfmanager(item, filtro_hoyos):
            continue

        precio = item.get("price")
        if precio is None:
            continue

        clave = (
            hora,
            item.get("resourceName", ""),
            jugadores_disp
        )

        if clave not in resultados_agrupados:
            resultados_agrupados[clave] = {
                "hora": hora,
                "jugadores_disponibles": jugadores_disp,
                "tarifas": []
            }

        resultados_agrupados[clave]["tarifas"].append({
            "nombre": (item.get("name") or item.get("categoryName") or "Tarifa").strip(),
            "precio": precio
        })

    for grupo in resultados_agrupados.values():
        resultados.append(
            construir_resultado(
                campo,
                recorrido,
                grupo["hora"],
                grupo["jugadores_disponibles"],
                grupo["tarifas"]
            )
        )

    return resultados


def buscar_teetimes(fecha, hora_inicio, hora_fin, jugadores, filtro_hoyos, filtro_tipo, campos_seleccionados=None, lat_ref=None, lon_ref=None, radio_km=None):
    campos = cargar_campos(solo_activos=True)

    if modo_debug:
        debug_herreria("01 - PARÁMETROS ENTRADA", {
            "fecha": fecha,
            "hora_inicio": hora_inicio,
            "hora_fin": hora_fin,
            "jugadores": jugadores,
            "filtro_hoyos": filtro_hoyos,
            "filtro_tipo": filtro_tipo,
            "campos_seleccionados": campos_seleccionados,
            "lat_ref": lat_ref,
            "lon_ref": lon_ref,
            "radio_km": radio_km
        })

        herrerias_cargadas = [
            {
                "nombre": campo.get("nombre"),
                "metodo": campo.get("metodo"),
                "activo": campo.get("activo", True),
                "lat": campo.get("lat"),
                "lon": campo.get("lon"),
                "num_recorridos": len(campo.get("Recorridos", [])),
                "recorridos": campo.get("Recorridos", [])
            }
            for campo in campos
            if es_herreria(campo)
        ]
        debug_herreria("02 - TRAS CARGAR CAMPOS ACTIVOS", {
            "total_campos_activos": len(campos),
            "herrerias_encontradas": herrerias_cargadas
        })

    if campos_seleccionados is not None:
        campos = [
            campo for campo in campos
            if campo["nombre"] in campos_seleccionados
        ]

        if modo_debug:
            debug_herreria("03 - TRAS FILTRO CAMPOS SELECCIONADOS", {
                "campos_seleccionados": campos_seleccionados,
                "total_tras_filtro": len(campos),
                "nombres_tras_filtro": [campo.get("nombre") for campo in campos],
                "sigue_herreria": any(es_herreria(campo) for campo in campos)
            })

    if lat_ref is not None and lon_ref is not None and radio_km is not None:
        campos_en_radio = []

        for campo in campos:
            lat_campo = campo.get("lat")
            lon_campo = campo.get("lon")

            if es_herreria(campo):
                debug_herreria("04 - ENTRA EN FILTRO RADIO", {
                    "nombre": campo.get("nombre"),
                    "lat_campo_original": lat_campo,
                    "lon_campo_original": lon_campo,
                    "lat_ref": lat_ref,
                    "lon_ref": lon_ref,
                    "radio_km": radio_km
                })

            try:
                lat_campo = float(lat_campo)
                lon_campo = float(lon_campo)
                lat_ref_float = float(lat_ref)
                lon_ref_float = float(lon_ref)
            except (TypeError, ValueError):
                if modo_debug:
                    st.warning(f"Campo sin coordenadas válidas: {campo.get('nombre', 'sin nombre')}")
                    if es_herreria(campo):
                        debug_herreria("04B - DESCARTADA POR COORDENADAS NO VÁLIDAS", {
                            "lat_campo": campo.get("lat"),
                            "lon_campo": campo.get("lon")
                        })
                continue

            distancia = calcular_distancia_km(
                lat_ref_float,
                lon_ref_float,
                lat_campo,
                lon_campo
            )

            if es_herreria(campo):
                debug_herreria("05 - DISTANCIA CALCULADA", {
                    "distancia": distancia,
                    "radio_km": radio_km,
                    "entra_en_radio": distancia <= float(radio_km)
                })

            if distancia <= float(radio_km):
                campo["distancia_km"] = distancia
                campos_en_radio.append(campo)

                if es_herreria(campo):
                    debug_herreria("06 - AÑADIDA A CAMPOS EN RADIO", {
                        "nombre": campo.get("nombre"),
                        "distancia_km": distancia
                    })

        campos = campos_en_radio

        if modo_debug:
            debug_herreria("07 - TRAS FILTRO RADIO", {
                "total_campos_en_radio": len(campos),
                "nombres_en_radio": [campo.get("nombre") for campo in campos],
                "sigue_herreria": any(es_herreria(campo) for campo in campos)
            })

    resultados = []

    for campo in campos:
        metodo = campo.get("metodo", "teeone_v1")

        if modo_debug and es_herreria(campo):
            debug_herreria("08 - ANTES DE CONSULTAR PROVEEDOR", {
                "nombre": campo.get("nombre"),
                "metodo": metodo,
                "recorridos": campo.get("Recorridos", [])
            })

        if metodo == "teeone_v1":
            resultados.extend(
                consultar_campo_teeone_v1(
                    campo, fecha, hora_inicio, hora_fin, jugadores,
                    filtro_hoyos, filtro_tipo
                )
            )
        elif metodo == "teeone_v2":
            resultados.extend(
                consultar_campo_teeone_v2(
                    campo, fecha, hora_inicio, hora_fin, jugadores,
                    filtro_hoyos, filtro_tipo
                )
            )
        elif metodo == "golfmanager":
            resultados.extend(
                consultar_campo_golfmanager(
                    campo, fecha, hora_inicio, hora_fin, jugadores,
                    filtro_hoyos, filtro_tipo
                )
            )
        elif metodo == "golfmanager_v2":
            resultados.extend(
                consultar_campo_golfmanager_v2(
                    campo, fecha, hora_inicio, hora_fin, jugadores,
                    filtro_hoyos, filtro_tipo
                )
            )
        elif modo_debug:
            st.warning(f"Método no soportado para {campo.get('nombre', 'campo sin nombre')}: {metodo}")

    if modo_debug:
        debug_herreria("09 - RESULTADOS FINALES", {
            "total_resultados": len(resultados),
            "resultados_herreria": [r for r in resultados if "herrer" in str(r.get("campo", "")).lower()]
        })

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

/* Slider - zona seleccionada */
.stSlider [data-baseweb="slider"] > div > div:nth-child(2) {
    background-color: #9aa3ad !important;
}

/* Slider - puntos/handles */
.stSlider [role="slider"] {
    background-color: #9aa3ad !important;
    border-color: #9aa3ad !important;
    box-shadow: none !important;
}

/* Slider - etiquetas de valores para distancia y rango horario */
.stSlider [data-testid="stThumbValue"] {
    color: #1f2933 !important;
    background-color: transparent !important;
    font-size: 16px !important;
    font-weight: 600 !important;
}

/* Reducir separación */
div[data-testid="column"] {
    padding-left: 0.10rem !important;
    padding-right: 0.10rem !important;
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

if "jugadores" not in st.session_state:
    st.session_state.jugadores = None

if "hoyos_seleccionados" not in st.session_state:
    st.session_state.hoyos_seleccionados = ["18", "9"]

if "tipo_seleccionado" not in st.session_state:
    st.session_state.tipo_seleccionado = ["largo", "corto"]

def obtener_fecha_horas_default():
    ahora = datetime.now(TZ)

    if ahora.hour >= 18:
        fecha_default = ahora.date() + timedelta(days=1)
        hora_inicio_default = time(7, 0)
    else:
        fecha_default = ahora.date()
        hora_inicio_default = redondear_hora_actual()

    hora_fin_default_dt = datetime.combine(fecha_default, hora_inicio_default) + timedelta(hours=1)
    hora_fin_default = min(hora_fin_default_dt.time(), time(20, 0))

    return fecha_default, hora_inicio_default, hora_fin_default

fecha_default, hora_inicio_default, hora_fin_default = obtener_fecha_horas_default()

with st.container(border=True):
    st.markdown("### 🔎 Criterios de búsqueda")

    localidades = cargar_localidades()

    lista_localidades = [
        f"{l['localidad']} ({l['provincia']})"
        for l in localidades
    ]

    localidad_seleccionada = st.selectbox(
        "Localidad",
        options=lista_localidades,
        index=None,
        placeholder="Selecciona una localidad"
    )

    radio_km = st.slider(
        "Radio de búsqueda (km)",
        min_value=0,
        max_value=100,
        value=10,
        step=10,
        key="radio_busqueda_km_v2"
    )

    col1, col2 = st.columns([1, 2])

    with col1:
        fecha = st.date_input(
            "Fecha",
            value=fecha_default,
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

    col3, col4, col5 = st.columns([1.4, 1, 1])

    with col3:
        jugadores_tmp = st.segmented_control(
            "Jugadores",
            options=[1, 2, 3, 4],
            format_func=lambda x: f"🏌️ x {x}",
            default=4,
            selection_mode="single",
            key="jugadores_segmented"
        )
        
        jugadores = jugadores_tmp

    with col4:
        hoyos_tmp = st.segmented_control(
            "Hoyos",
            options=["18", "9"],
            default=st.session_state.hoyos_seleccionados,
            selection_mode="multi",
            key="hoyos_segmented"
        )
    
        if set(hoyos_tmp) == {"18", "9"}:
            filtro_hoyos = "todos"
        elif hoyos_tmp == ["18"]:
            filtro_hoyos = "18"
        elif hoyos_tmp == ["9"]:
            filtro_hoyos = "9"
        else:
            filtro_hoyos = None

    with col5:
        tipo_tmp = st.segmented_control(
            "Tipo campo",
            options=["largo", "corto"],
            format_func=lambda x: x.capitalize(),
            default=st.session_state.tipo_seleccionado,
            selection_mode="multi",
            key="tipo_segmented"
        )
    
        if set(tipo_tmp) == {"largo", "corto"}:
            filtro_tipo = "todos"
        elif tipo_tmp == ["largo"]:
            filtro_tipo = "largo"
        elif tipo_tmp == ["corto"]:
            filtro_tipo = "corto"
        else:
            filtro_tipo = None

    hora_inicio_txt = hora_inicio.strftime("%H:%M")
    hora_fin_txt = hora_fin.strftime("%H:%M")

    campos_seleccionados_debug = None
    mostrar_payloads_debug = False
    mostrar_responses_debug = False

    if modo_debug:
        campos_debug = cargar_campos(solo_activos=True)
        nombres_campos_debug = sorted([campo["nombre"] for campo in campos_debug])

        st.markdown("### 🧪 Debug")

        campos_seleccionados_debug = st.multiselect(
            "Campos a consultar",
            options=nombres_campos_debug,
            default=[]
        )

        mostrar_payloads_debug = st.checkbox("Mostrar payloads enviados", value=False)
        mostrar_responses_debug = st.checkbox("Mostrar responses recibidas", value=False)

if st.button("Buscar"):
        
    if modo_debug:
        st.session_state.debug_payloads = []
        st.session_state.debug_responses = []
        
    if localidad_seleccionada is None:
        st.error("Debes seleccionar una localidad.")
        st.stop()

    localidad_obj = next(
        l for l in localidades
        if f"{l['localidad']} ({l['provincia']})" == localidad_seleccionada
    )

    lat_ref = localidad_obj["lat"]
    lon_ref = localidad_obj["lon"]

    if jugadores is None or filtro_hoyos is None or filtro_tipo is None:
        st.error("Falta algún campo de búsqueda por seleccionar")
        st.stop()
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
        filtro_tipo,
        campos_seleccionados_debug,
        lat_ref,
        lon_ref,
        radio_km
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
                    titulo_campo = r['campo']
                    if modo_debug:
                        titulo_campo = "🧪 " + titulo_campo
                        
                    distancia_txt = ""
                    if r.get("distancia_km") is not None:
                        distancia_txt = f"📍 {round(r['distancia_km'],1)} km"
                        
                    st.markdown(f"""
                    <div class="result-card">
                        <div class="result-title">{titulo_campo}</div>
                        <div class="result-meta">{distancia_txt} · 🕒 <b>{r['hora']}</b> · 🏌️ x {r['jugadores_disponibles']}</div>
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

if modo_debug:
    if mostrar_payloads_debug or mostrar_responses_debug:
        st.markdown("### 🧪 Trazas debug")

        if mostrar_payloads_debug:
            pintar_caja_debug("Payloads enviados", st.session_state.debug_payloads)

        if mostrar_responses_debug:
            pintar_caja_debug("Responses recibidas", st.session_state.debug_responses)

st.markdown("------")

st.markdown(
    "<p style='text-align:center; font-size:12px; color:gray;'>v2.0 - BETA()</p>",
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

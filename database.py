# database.py

import pickle
import os

# Variables globales
propuestas = {}
votos = {}
participacion = {}

ARCHIVO = "datos.pkl"

# Cargar datos si existen
if os.path.exists(ARCHIVO):
    with open(ARCHIVO, "rb") as f:
        propuestas, votos, participacion = pickle.load(f)

def guardar_datos():
    with open(ARCHIVO, "wb") as f:
        pickle.dump((propuestas, votos, participacion), f)

def registrar_propuesta(texto, user):
    pid = max(propuestas.keys(), default=0) + 1
    propuestas[pid] = {
        "texto": texto,
        "uid_autor": user.id,
        "nombre_autor": user.first_name,
        "votos": 0
    }
    participacion[user.id] = participacion.get(user.id, 0) + 1
    return pid

def borrar_propuesta(pid, uid):
    if pid not in propuestas:
        return "❌ Propuesta no encontrada."
    if propuestas[pid]["uid_autor"] != uid:
        return "❌ Solo el autor puede borrar su propuesta."
    
    del propuestas[pid]
    return "✅ Propuesta eliminada."

def votar_por_propuesta(pid, uid):
    if pid not in propuestas:
        return "❌ Propuesta no encontrada."
    if uid in votos and votos[uid] == pid:
        return "❌ Ya votaste por esta propuesta."
    
    # Si ya votó antes por otra, restar voto anterior
    if uid in votos:
        anterior = votos[uid]
        if anterior in propuestas:
            propuestas[anterior]["votos"] -= 1

    votos[uid] = pid
    propuestas[pid]["votos"] += 1
    return "✅ Voto registrado."

def get_propuesta_id(pid):
    return propuestas.get(pid)

def reiniciar_datos():
    global propuestas, votos, participacion
    propuestas.clear()
    votos.clear()
    participacion.clear()
    guardar_datos()

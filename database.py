# database.py
import pickle
import os
from collections import defaultdict

DATA_FILE = "data.pkl"

# Datos globales
propuestas = {}
votos = defaultdict(set)
participacion = defaultdict(int)
_propuesta_id = 1

# Cargar si existe
if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "rb") as f:
        propuestas, votos, participacion, _propuesta_id = pickle.load(f)

def guardar_datos():
    with open(DATA_FILE, "wb") as f:
        pickle.dump((propuestas, votos, participacion, _propuesta_id), f)

def get_propuesta_id():
    global _propuesta_id
    return _propuesta_id

def registrar_propuesta(texto, user):
    global _propuesta_id
    propuestas[_propuesta_id] = {
        "texto": texto,
        "autor": user.id,
        "nombre_autor": user.first_name,
        "votos": 0
    }
    participacion[user.id] += 1
    pid = _propuesta_id
    _propuesta_id += 1
    return pid

def votar_por_propuesta(pid, uid):
    if pid not in propuestas:
        return "❌ La propuesta no existe."
    if uid in votos[pid]:
        return "⚠️ Ya has votado por esta propuesta."

    votos[pid].add(uid)
    propuestas[pid]["votos"] += 1
    return "✅ ¡Voto registrado!"

def borrar_propuesta(pid, uid):
    if pid not in propuestas:
        return "❌ No existe esa propuesta."
    if propuestas[pid]["autor"] != uid:
        return "⚠️ Solo el autor puede borrar su propuesta."

    del propuestas[pid]
    votos.pop(pid, None)
    return f"🗑️ Propuesta #{pid} borrada."

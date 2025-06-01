import os
import httpx
import logging
from typing import List, Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO)

# Variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

if not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("❌ Las variables de entorno SUPABASE_URL y SUPABASE_ANON_KEY deben estar definidas.")

# Headers para Supabase
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Tablas
PROPOSALS_TABLE = "proposals"
VOTES_TABLE = "votes"
PARTICIPATION_TABLE = "participation"

# ✅ Registrar nueva propuesta
async def registrar_propuesta(texto: str, user) -> int:
    async with httpx.AsyncClient() as client:
        payload = {
            "texto": texto,
            "uid_autor": user.id,
            "nombre_autor": user.first_name
        }
        try:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}",
                headers={**HEADERS, "Prefer": "return=representation"},
                json=payload
            )
            resp.raise_for_status()
            data = resp.json()
            if not data:
                raise ValueError("❌ Error al insertar propuesta.")
            pid = data[0]["id"]

            # Actualizar participación
            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
                headers=HEADERS,
                json={"uid_input": user.id, "nombre_input": user.first_name}
            )
            return pid
        except Exception as e:
            logging.error(f"Error registrando propuesta: {e}")
            raise

# ✅ Obtener propuestas
async def obtener_propuestas() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=*&order=id.asc",
                headers=HEADERS
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error(f"Error obteniendo propuestas: {e}")
            return []

# ✅ Votar por propuesta
async def votar_por_propuesta(pid: int, uid: int, nombre: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            # Ya votó
            check = await client.get(
                f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=eq.{uid}&proposal_id=eq.{pid}",
                headers=HEADERS
            )
            if check.json():
                return "⚠️ Ya has votado por esta propuesta."

            # Insertar voto
            await client.post(
                f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}",
                headers=HEADERS,
                json={"uid": uid, "proposal_id": pid}
            )

            # Obtener votos actuales
            votos_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=votos&id=eq.{pid}",
                headers=HEADERS
            )
            votos_data = votos_resp.json()
            votos_actuales = votos_data[0].get("votos", 0)

            # Actualizar contador
            await client.patch(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
                headers=HEADERS,
                json={"votos": votos_actuales + 1}
            )

            # Actualizar participación
            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
                headers=HEADERS,
                json={"uid_input": uid, "nombre_input": nombre}
            )

            return "✅ ¡Voto registrado!"

        except Exception as e:
            logging.error(f"Error votando por propuesta: {e}")
            return "❌ Error al votar."

# ✅ Borrar propuesta
async def borrar_propuesta(pid: int, uid: int) -> str:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=uid_autor&id=eq.{pid}",
                headers=HEADERS
            )
            data = resp.json()
            if not data:
                return "❌ Propuesta no encontrada."

            autor_id = data[0]["uid_autor"]
            if uid != autor_id and uid != ADMIN_ID:
                return "🚫 Solo el autor o el admin pueden borrar esta propuesta."

            # Borrar votos y propuesta
            await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?proposal_id=eq.{pid}", headers=HEADERS)
            await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}", headers=HEADERS)

            return "✅ Propuesta eliminada."

        except Exception as e:
            logging.error(f"Error borrando propuesta: {e}")
            return "❌ Error al intentar eliminar."

# ✅ Top propuestas
async def obtener_top_propuestas(limit: int = 5) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=*&order=votos.desc&limit={limit}",
                headers=HEADERS
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error(f"Error obteniendo top propuestas: {e}")
            return []

# ✅ Participación
async def obtener_participacion() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?select=*&order=count.desc",
                headers=HEADERS
            )
            resp.raise_for_status()
            return resp.json()
        except Exception as e:
            logging.error(f"Error obteniendo participación: {e}")
            return []

# ✅ Reset general
async def reiniciar_datos():
    async with httpx.AsyncClient() as client:
        try:
            await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=gt.0", headers=HEADERS)
            await client.delete(f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?uid=gt.0", headers=HEADERS)
            await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=gt.0", headers=HEADERS)
            await reiniciar_conteo_propuestas()
        except Exception as e:
            logging.error(f"Error al reiniciar datos: {e}")

# ✅ Reset secuencia de IDs
async def reiniciar_conteo_propuestas():
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/reset_proposal_id_sequence",
                headers=HEADERS,
                json={}
            )
        except Exception as e:
            logging.error(f"Error al reiniciar secuencia de IDs: {e}")

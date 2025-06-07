import os
import httpx
import logging
from typing import List, Dict, Any

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

# ✅ Registrar propuesta
async def registrar_propuesta(texto, usuario):
    uid = usuario.id
    nombre = usuario.full_name

    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/insertar_participacion_si_no_existe",
                headers=HEADERS,
                json={"uid": uid, "nombre": nombre}
            )

            data = {
                "uid_autor": uid,
                "contenido": texto,
                "votos": 0
            }

            response = await client.post(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}",
                headers=HEADERS,
                json=data
            )

            if response.status_code >= 400 or not response.text.strip():
                logger.error("❌ Respuesta vacía o con error HTTP (%s): %s", response.status_code, response.text)
                raise ValueError("Respuesta vacía o no válida al insertar propuesta.")

            try:
                json_data = await response.json()
            except Exception:
                logger.error("❌ No se pudo convertir a JSON: %s", response.text)
                raise ValueError("Respuesta no válida al insertar propuesta.")

            if isinstance(json_data, list) and json_data:
                pid = json_data[0].get("id")
            elif isinstance(json_data, dict) and "id" in json_data:
                pid = json_data["id"]
            else:
                logger.error("❌ Respuesta inesperada al insertar propuesta: %s", json_data)
                raise ValueError("Respuesta inesperada al insertar propuesta.")

            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
                headers=HEADERS,
                json={"uid_input": uid, "nombre_input": usuario.first_name}
            )

            return pid

        except Exception as e:
            logger.error(f"Error registrando propuesta: {e}")
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
            logger.error(f"Error obteniendo propuestas: {e}")
            return []

# ✅ Votar por propuesta
async def votar_por_propuesta(pid: int, uid: int, nombre: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            check = await client.get(
                f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=eq.{uid}&proposal_id=eq.{pid}",
                headers=HEADERS
            )
            check.raise_for_status()
            if check.json():
                return "⚠️ Ya has votado por esta propuesta."

            await client.post(
                f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}",
                headers=HEADERS,
                json={"uid": uid, "proposal_id": pid}
            )

            votos_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=votos&id=eq.{pid}",
                headers=HEADERS
            )
            votos_resp.raise_for_status()
            votos_data = votos_resp.json()

            if not votos_data:
                return "❌ Propuesta no encontrada."

            votos_actuales = votos_data[0].get("votos", 0)

            await client.patch(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
                headers=HEADERS,
                json={"votos": votos_actuales + 1}
            )

            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
                headers=HEADERS,
                json={"uid_input": uid, "nombre_input": nombre}
            )

            return "✅ ¡Voto registrado!"
        except Exception as e:
            logger.error(f"Error votando por propuesta: {e}")
            return "❌ Error al votar."

# ✅ Borrar propuesta
async def borrar_propuesta(pid: int, uid: int) -> str:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=uid_autor&id=eq.{pid}",
                headers=HEADERS
            )
            resp.raise_for_status()
            data = resp.json()

            if not data:
                return "❌ Propuesta no encontrada."

            autor_id = data[0]["uid_autor"]
            if uid != autor_id and uid != ADMIN_ID:
                return "🚫 Solo el autor o el admin pueden borrar esta propuesta."

            await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?proposal_id=eq.{pid}", headers=HEADERS)
            await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}", headers=HEADERS)

            return "✅ Propuesta eliminada."
        except Exception as e:
            logger.error(f"Error borrando propuesta: {e}")
            return "❌ Error al intentar eliminar."

# ✅ Obtener top propuestas
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
            logger.error(f"Error obteniendo top propuestas: {e}")
            return []

# ✅ Obtener participación
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
            logger.error(f"Error obteniendo participación: {e}")
            return []

# ✅ Reiniciar todo
async def reiniciar_datos() -> None:
    async with httpx.AsyncClient() as client:
        try:
            await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=gt.0", headers=HEADERS)
            await client.delete(f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?uid=gt.0", headers=HEADERS)
            await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=gt.0", headers=HEADERS)
            await reiniciar_conteo_propuestas()
        except Exception as e:
            logger.error(f"Error al reiniciar datos: {e}")

# ✅ Reiniciar secuencia de IDs
async def reiniciar_conteo_propuestas() -> None:
    async with httpx.AsyncClient() as client:
        try:
            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/reset_proposal_id_sequence",
                headers=HEADERS,
                json={}
            )
        except Exception as e:
            logger.error(f"Error al reiniciar secuencia de IDs: {e}")

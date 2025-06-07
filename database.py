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

HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json",
    "Prefer": "return=representation"  # 👈 Esto es crucial
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

            try:
                json_data = response.json()  # ❌ No usar await aquí
            except Exception:
                logger.error("❌ No se pudo convertir a JSON: %s", response.text)
                raise ValueError("Respuesta no válida al insertar propuesta.")

            if isinstance(json_data, list) and json_data:
                pid = json_data[0].get("id")
            elif isinstance(json_data, dict) and "id" in json_data:
                pid = json_data["id"]
            else:
                raise ValueError("❌ Respuesta inesperada al insertar propuesta: %s" % json_data)

            await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
                headers=HEADERS,
                json={"uid_input": uid, "nombre_input": usuario.first_name}
            )

            return pid

        except Exception as e:
            logger.error(f"Error registrando propuesta: {e}")
            raise

# ✅ Ver propuestas
async def verpropuestas(update: Update, context: ContextTypes.DEFAULT_TYPE):
    propuestas = await obtener_propuestas()

    if not propuestas:
        await update.message.reply_text("No hay propuestas registradas aún.")
        return

    mensaje = "📋 *Lista de propuestas:*\n\n"
    for p in propuestas:
        nombre = p.get("nombre_autor", "Anónimo")
        mensaje += f"#{p['id']}: {p['contenido']} (👤 {nombre}, 👍 {p['votos']})\n"

    await update.message.reply_text(mensaje, parse_mode=ParseMode.MARKDOWN)

# ✅ Votar por propuesta
async def votar_por_propuesta(pid: int, uid: int, nombre: str) -> str:
    async with httpx.AsyncClient() as client:
        try:
            # 1. Verificar si ya ha votado
            check_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=eq.{uid}&proposal_id=eq.{pid}",
                headers=HEADERS
            )
            check_resp.raise_for_status()
            votos_previos = check_resp.json()
            if votos_previos:
                return "⚠️ Ya has votado por esta propuesta."

            # 2. Registrar el voto
            voto_resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}",
                headers=HEADERS,
                json={"uid": uid, "proposal_id": pid}
            )
            voto_resp.raise_for_status()

            # 3. Obtener votos actuales de la propuesta
            votos_resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=votos&id=eq.{pid}",
                headers=HEADERS
            )
            votos_resp.raise_for_status()
            votos_data = votos_resp.json()

            if not votos_data:
                return "❌ Propuesta no encontrada."

            votos_actuales = votos_data[0].get("votos", 0)

            # 4. Incrementar votos de la propuesta
            patch_resp = await client.patch(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
                headers=HEADERS,
                json={"votos": votos_actuales + 1}
            )
            patch_resp.raise_for_status()

            # 5. Incrementar participación
            participacion_resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
                headers=HEADERS,
                json={"uid_input": uid, "nombre_input": nombre}
            )
            participacion_resp.raise_for_status()

            return "✅ ¡Voto registrado!"
        
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error al votar: {e.response.status_code} - {e.response.text}")
            return "❌ Error al votar (HTTP)."
        except Exception as e:
            logger.error(f"❌ Error inesperado al votar: {e}")
            return "❌ Error inesperado al votar."

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
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=id,uid_autor,contenido,votos,created_at&order=votos.desc&limit={limit}",
                headers=HEADERS
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                logger.error("❌ Formato inesperado en respuesta de top propuestas")
                return []

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error obteniendo top propuestas: {e.response.status_code} - {e.response.text}")
            return []

        except Exception as e:
            logger.error(f"❌ Error inesperado obteniendo top propuestas: {e}")
            return []


# ✅ Obtener participación
async def obtener_participacion() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(
                f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?select=uid,nombre,count&order=count.desc",
                headers=HEADERS
            )
            resp.raise_for_status()
            data = resp.json()

            if not isinstance(data, list):
                logger.error("❌ Formato inesperado en respuesta de participación")
                return []

            return data

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error obteniendo participación: {e.response.status_code} - {e.response.text}")
            return []

        except Exception as e:
            logger.error(f"❌ Error inesperado obteniendo participación: {e}")
            return []

# ✅ Reiniciar todo
async def reiniciar_datos() -> None:
    async with httpx.AsyncClient() as client:
        try:
            # Eliminar votos
            r1 = await client.delete(
                f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=gt.0",
                headers=HEADERS
            )
            r1.raise_for_status()

            # Eliminar participación
            r2 = await client.delete(
                f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?uid=gt.0",
                headers=HEADERS
            )
            r2.raise_for_status()

            # Eliminar propuestas
            r3 = await client.delete(
                f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=gt.0",
                headers=HEADERS
            )
            r3.raise_for_status()

            # Reiniciar el conteo (por ejemplo, si llevas un ID o log de propuestas)
            await reiniciar_conteo_propuestas()

            logger.info("✅ Datos reiniciados correctamente.")

        except httpx.HTTPStatusError as e:
            logger.error(f"❌ HTTP error al reiniciar datos: {e.response.status_code} - {e.response.text}")

        except Exception as e:
            logger.error(f"❌ Error inesperado al reiniciar datos: {e}")

# ✅ Reiniciar secuencia de IDs
async def reiniciar_conteo_propuestas() -> None:
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(
                f"{SUPABASE_URL}/rest/v1/rpc/reset_proposal_id_sequence",
                headers=HEADERS,
                json={}
            )
            resp.raise_for_status()
            logger.info("✅ Secuencia de IDs reiniciada correctamente.")
        except httpx.HTTPStatusError as e:
            logger.error(f"❌ Error HTTP al reiniciar secuencia: {e.response.status_code} - {e.response.text}")
        except Exception as e:
            logger.error(f"❌ Error inesperado al reiniciar secuencia de IDs: {e}")

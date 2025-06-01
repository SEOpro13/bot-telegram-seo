import os
import httpx
from typing import List, Dict, Any

# Configuración de Supabase REST
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

# Nombres de tablas
PROPOSALS_TABLE = "proposals"
VOTES_TABLE = "votes"
PARTICIPATION_TABLE = "participation"

# ID del administrador
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))

async def registrar_propuesta(texto: str, user) -> int:
    async with httpx.AsyncClient() as client:
        headers = HEADERS.copy()
        headers["Prefer"] = "return=representation"

        payload = {
            "texto": texto,
            "uid_autor": user.id,
            "nombre_autor": user.first_name
        }

        # Insertar propuesta
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()[0]
        pid = data["id"]

        # Llamar a la función Supabase para aumentar participación
        await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
            headers=HEADERS,
            json={"uid_input": user.id}
        )

    return pid

async def obtener_propuestas() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=*&order=id.asc",
            headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()

async def votar_por_propuesta(pid: int, uid: int, nombre: str) -> str:
    async with httpx.AsyncClient() as client:
        # Verificar si ya votó
        check = await client.get(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=eq.{uid}&proposal_id=eq.{pid}",
            headers=HEADERS
        )
        if check.json():
            return "⚠️ Ya has votado por esta propuesta."

        # Registrar el voto
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}",
            headers=HEADERS,
            json={"uid": uid, "proposal_id": pid}
        )

        # Obtener votos actuales
        resp2 = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=votos&id=eq.{pid}",
            headers=HEADERS
        )
        votos_actuales = resp2.json()[0]["votos"]

        # Incrementar conteo de votos
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
            headers=HEADERS,
            json={"votos": votos_actuales + 1}
        )

        # Llamar a la función para incrementar participación
        await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
            headers=HEADERS,
            json={"uid_input": uid}
        )

    return "✅ ¡Voto registrado!"

async def borrar_propuesta(pid: int, uid: int) -> str:
    async with httpx.AsyncClient() as client:
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

        await client.delete(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?proposal_id=eq.{pid}",
            headers=HEADERS
        )
        await client.delete(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
            headers=HEADERS
        )

    return "✅ Propuesta eliminada."

async def obtener_top_propuestas(limit: int = 5) -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=*&order=votos.desc&limit={limit}",
            headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()

async def obtener_participacion() -> List[Dict[str, Any]]:
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?select=*&order=count.desc",
            headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()

async def reiniciar_datos():
    """Elimina todas las propuestas, votos y participaciones"""
    async with httpx.AsyncClient() as client:
        await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=gt.0", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?uid=gt.0", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=gt.0", headers=HEADERS)

        # Llamar a función que reinicia la secuencia del ID
        await reiniciar_conteo_propuestas()

async def reiniciar_conteo_propuestas():
    """Llama la función en Supabase para reiniciar el ID de propuestas a 1"""
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/reset_proposal_id_sequence",
            headers=HEADERS,
            json={}
        )

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

# ID del administrador (puede venir desde config externa también)
ADMIN_ID = int(os.getenv("ADMIN_ID", 0))  # asegúrate de definir ADMIN_ID en tu entorno

async def registrar_propuesta(texto: str, user) -> int:
    async with httpx.AsyncClient() as client:
        headers = HEADERS.copy()
        headers["Prefer"] = "return=representation"

        payload = {"texto": texto, "uid_autor": user.id, "nombre_autor": user.first_name}
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()[0]
        pid = data["id"]

        up_headers = HEADERS.copy()
        up_headers["Prefer"] = "resolution=merge-duplicates"
        upsert_payload = {"uid": user.id, "nombre": user.first_name, "count": 1}
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?on_conflict=uid",
            headers=up_headers,
            json=upsert_payload
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
        check = await client.get(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=eq.{uid}&proposal_id=eq.{pid}",
            headers=HEADERS
        )
        if check.json():
            return "⚠️ Ya has votado por esta propuesta."

        await client.post(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}",
            headers=HEADERS,
            json={"uid": uid, "proposal_id": pid}
        )

        resp2 = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=votos&id=eq.{pid}",
            headers=HEADERS
        )
        votos_actuales = resp2.json()[0]["votos"]

        await client.patch(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
            headers=HEADERS,
            json={"votos": votos_actuales + 1}
        )

        up_headers = HEADERS.copy()
        up_headers["Prefer"] = "resolution=merge-duplicates"
        upsert_payload = {"uid": uid, "nombre": nombre, "count": 1}
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?on_conflict=uid",
            headers=up_headers,
            json=upsert_payload
        )

    return "✅ ¡Voto registrado!"

async def borrar_propuesta(pid: int, uid: int) -> str:
    """Permite borrar propuesta si el usuario es autor o admin"""
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
    """Elimina completamente todos los registros de propuestas, votos y participación"""
    async with httpx.AsyncClient() as client:
        await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=gt.0", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?uid=gt.0", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=gt.0", headers=HEADERS)

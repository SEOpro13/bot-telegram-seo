import os
import httpx
from typing import List, Dict, Any

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
HEADERS = {
    "apikey": SUPABASE_KEY,
    "Authorization": f"Bearer {SUPABASE_KEY}",
    "Content-Type": "application/json"
}

PROPOSALS_TABLE = "proposals"
VOTES_TABLE = "votes"
PARTICIPATION_TABLE = "participation"
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

        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()[0]
        pid = data["id"]

        # Actualizar participación con nombre
        await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
            headers=HEADERS,
            json={"uid_input": user.id, "nombre_input": user.first_name}
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

        # Actualizar participación del votante
        await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/incrementar_participacion",
            headers=HEADERS,
            json={"uid_input": uid, "nombre_input": nombre}
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
    async with httpx.AsyncClient() as client:
        await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=gt.0", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?uid=gt.0", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=gt.0", headers=HEADERS)
        await reiniciar_conteo_propuestas()

async def reiniciar_conteo_propuestas():
    async with httpx.AsyncClient() as client:
        await client.post(
            f"{SUPABASE_URL}/rest/v1/rpc/reset_proposal_id_sequence",
            headers=HEADERS,
            json={}
        )

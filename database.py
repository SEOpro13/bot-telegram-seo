# database.py
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

async def registrar_propuesta(texto: str, user) -> int:
    async with httpx.AsyncClient() as client:
        # 1) Insertar propuesta
        payload = {"texto": texto, "uid_autor": user.id, "nombre_autor": user.first_name}
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?return=representation",
            headers=HEADERS,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()[0]
        pid = data["id"]

        # 2) Upsert participación
        upsert_payload = {"uid": user.id, "count": 1}
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?on_conflict=uid",
            headers=HEADERS,
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

async def votar_por_propuesta(pid: int, uid: int) -> str:
    async with httpx.AsyncClient() as client:
        # 1) Verificar voto previo
        check = await client.get(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?uid=eq.{uid}&proposal_id=eq.{pid}",
            headers=HEADERS
        )
        if check.json():
            return "⚠️ Ya has votado por esta propuesta."

        # 2) Insertar voto
        await client.post(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}",
            headers=HEADERS,
            json={"uid": uid, "proposal_id": pid}
        )

        # 3) Leer votos actuales
        resp2 = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=votos&id=eq.{pid}",
            headers=HEADERS
        )
        votos_actuales = resp2.json()[0]["votos"]

        # 4) PATCH con el nuevo conteo
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
            headers=HEADERS,
            json={"votos": votos_actuales + 1}
        )
    return "✅ ¡Voto registrado!"

async def borrar_propuesta(pid: int, uid: int) -> str:
    async with httpx.AsyncClient() as client:
        # 1) Validar autor
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=uid_autor&id=eq.{pid}",
            headers=HEADERS
        )
        data = resp.json()
        if not data or data[0]["uid_autor"] != uid:
            return "❌ Propuesta no encontrada o permiso denegado."

        # 2) Eliminar votos
        await client.delete(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?proposal_id=eq.{pid}",
            headers=HEADERS
        )
        # 3) Eliminar propuesta
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
        await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}", headers=HEADERS)

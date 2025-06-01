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
    """Inserta una nueva propuesta y actualiza la participación."""
    async with httpx.AsyncClient() as client:
        # Cabeceras para devolver la fila insertada
        headers = HEADERS.copy()
        headers["Prefer"] = "return=representation"

        # Insertar propuesta
        payload = {"texto": texto, "uid_autor": user.id, "nombre_autor": user.first_name}
        resp = await client.post(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        data = resp.json()[0]
        pid = data["id"]

        # Upsert participación: merge duplicates y sumar count
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
    """Recupera todas las propuestas ordenadas por ID ascendente."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=*&order=id.asc",
            headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()

async def votar_por_propuesta(pid: int, uid: int, nombre: str) -> str:
    """Registra un voto y actualiza el conteo de votos y la participación."""
    async with httpx.AsyncClient() as client:
        # Verificar si ya votó
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

        # Leer votos actuales
        resp2 = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=votos&id=eq.{pid}",
            headers=HEADERS
        )
        votos_actuales = resp2.json()[0]["votos"]

        # PATCH con el nuevo conteo
        await client.patch(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
            headers=HEADERS,
            json={"votos": votos_actuales + 1}
        )

        # Upsert participación: merge duplicates y sumar count
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
    """Elimina propuesta y votos asociados si el usuario es autor."""
    async with httpx.AsyncClient() as client:
        # Validar autor
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=uid_autor&id=eq.{pid}",
            headers=HEADERS
        )
        data = resp.json()
        if not data or data[0]["uid_autor"] != uid:
            return "❌ Propuesta no encontrada o permiso denegado."

        # Eliminar votos
        await client.delete(
            f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}?proposal_id=eq.{pid}",
            headers=HEADERS
        )
        # Eliminar propuesta
        await client.delete(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?id=eq.{pid}",
            headers=HEADERS
        )
    return "✅ Propuesta eliminada."

async def obtener_top_propuestas(limit: int = 5) -> List[Dict[str, Any]]:
    """Obtiene las top N propuestas por votos descendente."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}?select=*&order=votos.desc&limit={limit}",
            headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()

async def obtener_participacion() -> List[Dict[str, Any]]:
    """Recupera ranking de participación."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}?select=*&order=count.desc",
            headers=HEADERS
        )
        resp.raise_for_status()
        return resp.json()

async def reiniciar_datos():
    """Elimina todos los registros de las tablas."""
    async with httpx.AsyncClient() as client:
        await client.delete(f"{SUPABASE_URL}/rest/v1/{VOTES_TABLE}", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PARTICIPATION_TABLE}", headers=HEADERS)
        await client.delete(f"{SUPABASE_URL}/rest/v1/{PROPOSALS_TABLE}", headers=HEADERS)

import os
from supabase import create_client, Client

# Inicializa el cliente Supabase con variables de entorno
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_ANON_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ===== Funciones de Base de Datos =====

def registrar_propuesta(texto: str, user) -> int:
    """
    Inserta una nueva propuesta en la tabla 'proposals' y actualiza la participación.
    """
    data = {
        "texto": texto,
        "uid_autor": user.id,
        "nombre_autor": user.first_name
    }
    resp = supabase.table("proposals").insert(data).execute()
    pid = resp.data[0]["id"]

    # Upsert en participación
    supabase.table("participation").upsert(
        {"uid": user.id, "count": 1},
        on_conflict="uid"
    ).increment("count", 1).execute()

    return pid


def obtener_propuestas() -> list:
    """
    Devuelve todas las propuestas ordenadas por id ascendente.
    """
    res = supabase.table("proposals").select("*").order("id", ascending=True).execute()
    return res.data


def votar_por_propuesta(pid: int, uid: int) -> str:
    """
    Registra un voto, impide votos duplicados y actualiza el conteo.
    """
    exists = supabase.table("votes") \
        .select("*") \
        .eq("uid", uid).eq("proposal_id", pid) \
        .execute().data
    if exists:
        return "⚠️ Ya has votado por esta propuesta."

    # Inserta voto
    supabase.table("votes").insert({"uid": uid, "proposal_id": pid}).execute()
    # Incrementa votos en proposals
    supabase.table("proposals").update(
        {"votos": supabase.table("proposals").column("votos") + 1}
    ).eq("id", pid).execute()

    return "✅ ¡Voto registrado!"


def borrar_propuesta(pid: int, uid: int) -> str:
    """
    Elimina una propuesta si el usuario es el autor.
    """
    prop = supabase.table("proposals").select("uid_autor") \
        .eq("id", pid).execute().data
    if not prop:
        return "❌ Propuesta no encontrada."
    if prop[0]["uid_autor"] != uid:
        return "⚠️ Solo el autor puede borrar su propuesta."

    supabase.table("votes").delete().eq("proposal_id", pid).execute()
    supabase.table("proposals").delete().eq("id", pid).execute()
    return "✅ Propuesta eliminada."


def obtener_top_propuestas(limit: int = 5) -> list:
    """
    Devuelve las top N propuestas ordenadas por votos descendente.
    """
    res = supabase.table("proposals") \
        .select("*").order("votos", ascending=False).limit(limit).execute()
    return res.data


def obtener_participacion() -> list:
    """
    Devuelve el ranking de participación por usuario.
    """
    res = supabase.table("participation").select("*").order("count", ascending=False).execute()
    return res.data


def reiniciar_datos():
    """
    Elimina todas las filas de las tablas para empezar de cero.
    """
    supabase.table("votes").delete().neq("uid", -1).execute()
    supabase.table("participation").delete().neq("uid", -1).execute()
    supabase.table("proposals").delete().neq("id", -1).execute()

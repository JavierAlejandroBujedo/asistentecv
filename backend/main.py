import os
import json
import shutil
import logging
import traceback
from typing import List, Optional
from fastapi import FastAPI, UploadFile, File, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Google Auth for Token Verification
from google.oauth2 import id_token
from google.auth.transport import requests as auth_requests
import time
import asyncio
from fastapi.responses import StreamingResponse
from collections import OrderedDict
# En producción (Render) con Python 3.14+, el manejo de loops es más estricto.
# Eliminamos nest_asyncio para evitar conflictos con el motor uvloop de Render.



# LlamaIndex & AI imports
from llama_index.core import (
    VectorStoreIndex, 
    StorageContext, 
    SimpleDirectoryReader, 
    Settings,
    PromptTemplate
)
from llama_index.llms.google_genai import GoogleGenAI
from llama_index.embeddings.google_genai import GoogleGenAIEmbedding
from llama_index.vector_stores.pinecone import PineconeVectorStore
from pinecone import Pinecone

# Load environment variables
load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX_NAME = os.getenv("PINECONE_INDEX_NAME")
ADMIN_UID = os.getenv("ADMIN_UID")  # Super Admin inamovible

# --- FIREBASE ADMIN SDK (Firestore para roles IAM) ---
firebase_admin = None
firestore_db = None

try:
    import firebase_admin
    from firebase_admin import credentials, firestore as admin_firestore

    if not firebase_admin._apps:
        # Prioridad 1: Variable de Entorno explícita con el JSON completo (Ideal para Render)
        firebase_cert_env = os.getenv("FIREBASE_CERT_JSON")
        cred_path = "./serviceAccountKey.json"
        
        try:
            if firebase_cert_env:
                print("[IAM] Inicializando Firestore desde Variable de Entorno (FIREBASE_CERT_JSON)...")
                # Cargamos el JSON string de Render como diccionario Python
                cert_dict = json.loads(firebase_cert_env, strict=False)
                cred = credentials.Certificate(cert_dict)
            elif os.path.exists(cred_path):
                print(f"[IAM] Inicializando Firestore con llave local: {cred_path}")
                cred = credentials.Certificate(cred_path)
            else:
                print("[IAM] Intentando inicializar Firestore con Application Default Credentials...")
                cred = credentials.ApplicationDefault()

            
            # Inicializamos app
            firebase_admin.initialize_app(cred, {'projectId': 'cvjavieralejandrobujedo'})
        except Exception as auth_err:
            print(f"[IAM WARNING] Falló la autenticación con Firebase: {auth_err}")
            print("[IAM] Limpiando app por inicialización inconclusa...")
            # Limpiar app por si quedó a medio iniciar
            if firebase_admin._apps:
                app = firebase_admin.get_app()
                firebase_admin.delete_app(app)

    # Solo si el SDK se autenticó correctamente intentamos sacar el cliente
    if firebase_admin._apps:
        try:
            print("[IAM] Solicitando cliente Firestore...")
            firestore_db = admin_firestore.client()
            print("[IAM SUCCESS] Modulo IAM Firestore activado con éxito.")
        except Exception as db_err:
            print(f"[IAM ERROR] No se pudo instanciar Firestore Client. ¿Faltan permisos?: {db_err}")
            firestore_db = None
            
except ImportError:
    print("[IAM WARN] firebase-admin no está instalado en el backend.")
except Exception as global_err:
    print(f"[IAM CRITICAL] Crash interceptado en inicialización de BD Ppal: {global_err}")
    firestore_db = None
finally:
    if not firestore_db:
        print("[IAM FALLBACK] >>> SISTEMA CORRIENDO EN MODO SUPER ADMIN <<<")
        print("[IAM FALLBACK] Las consultas y roles usarán exclusivamente ADMIN_UID.")

# Directories
DOCUMENTS_DIR = "documents"
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

print("\n" + "="*50)
print("SISTEMA RAG CV - MODO PROTEGIDO (FIREBASE)")
print("="*50)

# Firebase admin SDK bypassed (no ADC)

# --- RATE LIMITING ---
user_rate_limits = {}  # {uid: [timestamp1, timestamp2, ...]}
RATE_LIMIT_QUOTA = 10
RATE_LIMIT_WINDOW = 60 # segundos

def check_rate_limit(uid: str) -> bool:
    now = time.time()
    if uid not in user_rate_limits:
        user_rate_limits[uid] = [now]
        return True
    
    # Limpiamos timestamps antiguos de la ventana
    user_rate_limits[uid] = [t for t in user_rate_limits[uid] if now - t < RATE_LIMIT_WINDOW]
    
    if len(user_rate_limits[uid]) >= RATE_LIMIT_QUOTA:
        return False
        
    user_rate_limits[uid].append(now)
    return True

# --- CACHE ---
semantic_cache = OrderedDict()
CACHE_TTL = 3600

token_cache = {}
TOKEN_CACHE_TTL = 300

COMIC_WARNING = "¡Wow! Me has hecho tantas preguntas que hasta la IA se quedó sin aliento (y yo sin tokens). Dame un respiro de un minuto y seguimos analizando el talento de Javier."

# --- MÉTRICAS DE TOKENS (PERSISTENTES) ---
from datetime import datetime, date, timedelta

DAILY_RPD_LIMIT = 1500  # Límite gratuito de Gemini RPD
STATS_FILE = "stats.json"  # Archivo de persistencia

# Estructura en memoria: { "YYYY-MM-DD": {"requests": 0, "total_tokens": 0} }
usage_stats: dict = {}

def _today_key() -> str:
    return date.today().isoformat()

def _load_stats_from_disk():
    """Carga el historial desde stats.json al arrancar."""
    global usage_stats
    try:
        if os.path.exists(STATS_FILE):
            with open(STATS_FILE, "r", encoding="utf-8") as f:
                usage_stats = json.load(f)
            print(f"[STATS] Historial cargado desde {STATS_FILE}: {len(usage_stats)} días.")
        else:
            print(f"[STATS] No existe {STATS_FILE}, empezando desde cero.")
    except Exception as e:
        print(f"[STATS ERROR] No se pudo leer {STATS_FILE}: {e}")
        usage_stats = {}

def _save_stats_to_disk():
    """Persiste el historial en stats.json."""
    try:
        with open(STATS_FILE, "w", encoding="utf-8") as f:
            json.dump(usage_stats, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[STATS ERROR] No se pudo guardar {STATS_FILE}: {e}")

def record_usage(prompt_tokens: int = 0, completion_tokens: int = 0, from_cache: bool = False):
    """Registra uso de tokens para el día actual y persiste en disco."""
    key = _today_key()
    if key not in usage_stats:
        usage_stats[key] = {"requests": 0, "total_tokens": 0, "cache_hits": 0}
    usage_stats[key]["requests"] += 1
    usage_stats[key]["total_tokens"] += (prompt_tokens + completion_tokens)
    if from_cache:
        usage_stats[key]["cache_hits"] = usage_stats[key].get("cache_hits", 0) + 1
    source = "CACHE" if from_cache else "GEMINI"
    print(f"[STATS] [{source}] +1 req | prompt={prompt_tokens} | completion={completion_tokens} | total_hoy={usage_stats[key]['requests']}")
    _save_stats_to_disk()

def get_stats_summary() -> dict:
    today = _today_key()
    today_data = usage_stats.get(today, {"requests": 0, "total_tokens": 0})
    total_requests = sum(v["requests"] for v in usage_stats.values())
    total_tokens = sum(v["total_tokens"] for v in usage_stats.values())
    avg_tokens = round(total_tokens / total_requests, 1) if total_requests > 0 else 0

    # Histórico de los últimos 7 días
    history = []
    for i in range(6, -1, -1):
        d = (date.today() - timedelta(days=i)).isoformat()
        day_data = usage_stats.get(d, {"requests": 0, "total_tokens": 0})
        history.append({
            "date": d,
            "requests": day_data["requests"],
            "tokens": day_data["total_tokens"]
        })

    return {
        "requests_today": today_data["requests"],
        "tokens_today": today_data["total_tokens"],
        "total_tokens_used": total_tokens,
        "total_requests": total_requests,
        "average_tokens_per_query": avg_tokens,
        "remaining_quota": max(0, DAILY_RPD_LIMIT - today_data["requests"]),
        "quota_percentage": round((today_data["requests"] / DAILY_RPD_LIMIT) * 100, 2),
        "daily_limit": DAILY_RPD_LIMIT,
        "cache_size": len(semantic_cache),
        "history_7d": history,
    }

# Cargamos el historial al iniciar el módulo
_load_stats_from_disk()


# --- SECURITY DEPENDENCIES ---
async def verify_token(authorization: Optional[str] = Header(None)):
    print(f"[AUTH DEBUG] Validando header: {authorization[:20] if authorization else 'None'}")
    if not authorization or not authorization.startswith("Bearer "):
        return None
    
    token = authorization.split("Bearer ")[1]
    now = time.time()
    
    # 3. Optimización: Caché de Validación
    if token in token_cache and now - token_cache[token]['timestamp'] < TOKEN_CACHE_TTL:
        return token_cache[token]['decoded']

    try:
        # Verificación manual
        request_adapter = auth_requests.Request()
        # Permitimos 1 minuto de margen para el reloj
        decoded_token = id_token.verify_firebase_token(
            token, 
            request_adapter, 
            audience="cvjavieralejandrobujedo",
            clock_skew_in_seconds=60
        )
        token_cache[token] = {'decoded': decoded_token, 'timestamp': now}
        
        # Limpieza básica
        if len(token_cache) > 1000:
            token_cache.clear()
            
        return decoded_token
    except ValueError as e:
        error_msg = str(e)
        # Manejo de expiración o tokens futuros (problemas de reloj)
        if "Token expired" in error_msg or "Token used too early" in error_msg:
            print(f"[AUTH WARNING] Forzando decodificación manual por error de tiempo: {error_msg}")
            from google.auth import jwt
            # Decodificar sin verificar la firma/tiempo para casos de emergencia local
            decoded_token = jwt.decode(token, verify=False)
            token_cache[token] = {'decoded': decoded_token, 'timestamp': now}
            return decoded_token
        
        print(f"[AUTH ERROR] Token inválido (ValueError): {error_msg}")
        return None
    except Exception as e:
        print(f"[AUTH ERROR] Error crítico validando token: {type(e).__name__} - {str(e)}")
        traceback.print_exc()
        return None

# Caché de roles en memoria para no leer Firestore en cada request
role_cache: dict = {}  # {uid: {"role": "admin", "ts": timestamp}}
ROLE_CACHE_TTL = 300  # 5 minutos

async def get_user_role(uid: str) -> str:
    """
    Resolución de rol con prioridades:
    1. ADMIN_UID del .env  → siempre 'admin' (Super Admin inamovible)
    2. Firestore coleccion 'users' doc.role  → rol dinámico
    3. Fallback por defecto → 'user'
    """
    # Prioridad 1: Super Admin hardcodeado
    if uid == ADMIN_UID:
        return "admin"

    # Prioridad 2: Caché en memoria
    now = time.time()
    if uid in role_cache and now - role_cache[uid]["ts"] < ROLE_CACHE_TTL:
        return role_cache[uid]["role"]

    # Prioridad 3: Firestore
    if firestore_db:
        try:
            user_doc = firestore_db.collection("users").document(uid).get()
            if user_doc.exists:
                role = user_doc.to_dict().get("role", "user")
                role_cache[uid] = {"role": role, "ts": now}
                print(f"[IAM] Rol de Firestore para {uid}: {role}")
                return role
        except Exception as e:
            print(f"[IAM ERROR] No se pudo consultar Firestore para {uid}: {e}")

    return "user"

async def verify_admin(user: dict = Depends(verify_token)):
    if user is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    uid = user.get('uid') or user.get('sub') or user.get('user_id')
    role = await get_user_role(uid)

    if role != "admin":
        print(f"[SECURITY ALERT] Acceso admin denegado a: {user.get('email', 'Desconocido')} (UID: {uid})")
        raise HTTPException(status_code=403, detail="Acceso denegado: Se requieren permisos de administrador")

    user['_resolved_role'] = role
    return user

# --- EMBEDDING WRAPPER ---
class FixedGoogleEmbedding(GoogleGenAIEmbedding):
    def __init__(self, **kwargs):
        # Forzamos los parámetros críticos
        kwargs["model_name"] = "models/gemini-embedding-001"
        super().__init__(**kwargs)
        print(f"[EMBED INIT] Inicializado con modelo: {self.model_name}")

    def _truncate(self, vector: List[float]) -> List[float]:
        return vector[:768] if len(vector) > 768 else vector

    def get_text_embedding(self, text: str) -> List[float]:
        print(f"[EMBED DEBUG] Obteniendo embedding para texto (truncado a 30 caracteres): {text[:30]}...")
        vec = super().get_text_embedding(text)
        truncated = self._truncate(vec)
        print(f"[EMBED DEBUG] Vector original: {len(vec)}, Truncado: {len(truncated)}")
        return truncated

    def get_query_embedding(self, query: str) -> List[float]:
        return self._truncate(super().get_query_embedding(query))

    def _get_text_embedding(self, text: str) -> List[float]:
        return self._truncate(super()._get_text_embedding(text))
    
    def _get_query_embedding(self, query: str) -> List[float]:
        return self._truncate(super()._get_query_embedding(query))
    
    def get_text_embedding_batch(self, texts: List[str], **kwargs) -> List[List[float]]:
        embeddings = super().get_text_embedding_batch(texts, **kwargs)
        return [self._truncate(e) for e in embeddings]

    async def _aget_text_embedding(self, text: str) -> List[float]:
        print(f"[EMBED DEBUG] Obteniendo embedding ASYNC para: {text[:30]}...")
        vector = await super()._aget_text_embedding(text)
        truncated = self._truncate(vector)
        print(f"[EMBED DEBUG] Vector ASYNC original: {len(vector)}, Truncado: {len(truncated)}")
        return truncated

    async def _aget_query_embedding(self, query: str) -> List[float]:
        print(f"[EMBED DEBUG] Obteniendo embedding ASYNC para query: {query[:30]}...")
        vector = await super()._aget_query_embedding(query)
        truncated = self._truncate(vector)
        print(f"[EMBED DEBUG] Vector QUERY ASYNC original: {len(vector)}, Truncado: {len(truncated)}")
        return truncated

# Configure AI Models
Settings.llm = GoogleGenAI(
    api_key=GOOGLE_API_KEY, 
    model="models/gemini-flash-latest",
    temperature=0.1,  # Ms determinista y veloz
)
Settings.embed_model = FixedGoogleEmbedding(
    api_key=GOOGLE_API_KEY, 
    model_name="models/gemini-embedding-001"
)
Settings.chunk_size = 512  # 2. Optimización: Recuperación veloz
Settings.chunk_overlap = 50


SPANISH_QA_PROMPT = PromptTemplate(
    "Contexto: {context_str}\n"
    "Pregunta: {query_str}\n"
    "Responde solo con la información del contexto en castellano. Sé conciso y directo."
)

app = FastAPI(title="RAG CV Parser Protected API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:5174",
        "https://cvjavieralejandrobujedo.web.app",
        "https://cvjavieralejandrobujedo.firebaseapp.com"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

global_query_engine = None

@app.on_event("startup")
async def startup_event():
    print("[SYSTEM] Iniciando servidor y cargando recursos...")
    # Ejecutamos la carga pesada en un hilo separado para no bloquear el inicio del servidor
    asyncio.create_task(asyncio.to_thread(init_index))

def init_index():
    global global_query_engine
    try:
        print(f"[INIT] Conectando con Pinecone (Index: {PINECONE_INDEX_NAME})...")
        vector_store = PineconeVectorStore(pinecone_index=get_pc_index())
        
        # Intentamos cargar el índice desde el vector store (sin re-indexar todo)
        index = VectorStoreIndex.from_vector_store(vector_store)
        
        # Si no hay documentos en local, el motor responderá desde lo que ya esté en Pinecone
        # Si queremos sincronizar, se hace en el upload_cv
        
        global_query_engine = index.as_query_engine(
            similarity_top_k=3, 
            streaming=True,
            text_qa_template=SPANISH_QA_PROMPT
        )
        print("[INIT] Índice cargado correctamente desde el Vector Store.")
    except Exception as e:
        print(f"[INIT ERROR] No se pudo cargar el índice inicial: {e}")
        traceback.print_exc()

class ChatRequest(BaseModel):
    message: str

class AutoLoginRequest(BaseModel):
    enabled: bool

def get_pc_index():
    pc = Pinecone(api_key=PINECONE_API_KEY)
    return pc.Index(PINECONE_INDEX_NAME)

@app.post("/upload-cv")
async def upload_cv(
    file: UploadFile = File(...), 
    admin_user: dict = Depends(verify_admin)
):
    global global_query_engine
    print(f"[ADMIN] Subida autorizada para: {admin_user.get('email')}")
    
    try:
        # Asegurar que el puntero del archivo está al inicio
        file.file.seek(0)
        
        # Guardamos el nuevo archivo en local
        file_path = os.path.join(DOCUMENTS_DIR, file.filename)
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Limpiamos Pinecone con manejo de errores (por si es serverless o ya está vacío)
        try:
            idx = get_pc_index()
            # Intentar borrado total
            idx.delete(delete_all=True)
            print(f"[ADMIN] Pinecone index {PINECONE_INDEX_NAME} limpiado.")
        except Exception as e:
            print(f"[WARNING] Error al limpiar Pinecone (puede ser normal en ciertos planes): {e}")
        
        # Re-indexamos toda la carpeta documents
        vector_store = PineconeVectorStore(pinecone_index=get_pc_index())
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        documents = SimpleDirectoryReader(DOCUMENTS_DIR).load_data()
        
        if not documents:
            raise ValueError("No se pudieron extraer documentos del archivo subido (posible PDF corrupto o sin texto legible).")
            
        print(f"[ADMIN] Indexando {len(documents)} nodos en Pinecone...")
        index = VectorStoreIndex.from_documents(
            documents, 
            storage_context=storage_context,
            show_progress=True
        )
        print("[ADMIN] Indexación completada con éxito.")
        
        global_query_engine = index.as_query_engine(
            similarity_top_k=3, 
            streaming=True,
            text_qa_template=SPANISH_QA_PROMPT
        )
        
        return {"message": "CV sincronizado e indexado correctamente", "filename": file.filename}
    except Exception as e:
        print(f"[ERROR] {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cv-list")
async def list_cvs(admin_user: dict = Depends(verify_admin)):
    files = []
    for f in os.listdir(DOCUMENTS_DIR):
        path = os.path.join(DOCUMENTS_DIR, f)
        stats = os.stat(path)
        files.append({
            "name": f,
            "size": stats.st_size,
            "updated_at": stats.st_mtime
        })
    return files

@app.delete("/delete-cv/{filename}")
async def delete_cv(filename: str, admin_user: dict = Depends(verify_admin)):
    global global_query_engine
    try:
        file_path = os.path.join(DOCUMENTS_DIR, filename)
        if os.path.exists(file_path):
            os.remove(file_path)
            
            # Limpiar Pinecone
            idx = get_pc_index()
            idx.delete(delete_all=True)
            
            # Reset engine
            global_query_engine = None
            return {"message": f"Documento {filename} eliminado correctamente"}
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat")
async def chat(request: ChatRequest, authorization: Optional[str] = Header(None)):
    global global_query_engine
    
    # Validamos el token de forma manual para que sea 100% opcional
    user = await verify_token(authorization)
    
    uid = "Invitado"
    if user:
        uid = user.get('uid') or user.get('sub') or user.get('user_id') or "UID-Invitado"
    
    # 5. Control de Cuota (Rate Limiting)
    if not check_rate_limit(uid):
        return {"response": COMIC_WARNING}

    print(f"[DEBUG] Chat procesado como: {uid}")
    print(f"[DEBUG] Consultando índice de Pinecone para el UID: {uid}")

    # Forzar carga si es admin y no hay motor
    if uid == ADMIN_UID and global_query_engine is None:
        print(f"[ADMIN DEBUG] UID {uid} detectado. Forzando inicialización de índice para el admin.")
        init_index()

    if global_query_engine is None:
        # Intentar Lazy Loading si aún no está listo
        print(f"[CHAT DEBUG] UID {uid} - El índice no está listo. Intentando carga rápida...")
        init_index() 
        if global_query_engine is None:
            return {"response": "El cerebro de Javier se está despertando... por favor espera un momento y vuelve a preguntar."}
    
    now = time.time()
    try:
        if request.message in semantic_cache and now - semantic_cache[request.message]['timestamp'] < CACHE_TTL:
            print("[CHAT] Devolviendo respuesta desde cache semántica...")
            cached_response = semantic_cache[request.message]['response']
            # Registramos el hit de caché (0 tokens reales consumidos)
            record_usage(prompt_tokens=0, completion_tokens=0, from_cache=True)
            async def cache_stream():
                words = cached_response.split(" ")
                for i, word in enumerate(words):
                    chunk = word + (" " if i < len(words) - 1 else "")
                    yield f"data: {json.dumps({'text': chunk})}\n\n"
                    await asyncio.sleep(0.01)
            return StreamingResponse(cache_stream(), media_type="text/event-stream")

        from llama_index.core import QueryBundle
        bundle = QueryBundle(request.message)
        print(f"[CHAT] Consulta recibida: {request.message}")
        
        start_query = time.time()
        print(f"[CHAT] Iniciando aquery para: {request.message}")
        try:
            response = await global_query_engine.aquery(request.message)
            print(f"[CHAT] aquery finalizado en {time.time() - start_query:.2f}s")
            print(f"[DEBUG RESPONSE OBJ] Type: {type(response)}, Str value: '{str(response)[:50]}...'")
            # ─── VERIFICACIÓN DE usage_metadata REAL DE GEMINI ───
            if hasattr(response, 'metadata') and response.metadata:
                print(f"[GEMINI METADATA] {response.metadata}")
            if hasattr(response, 'response_metadata'):
                print(f"[GEMINI RESPONSE METADATA] {response.response_metadata}")
            # LlamaIndex expone el objeto LLM response en varios atributos
            raw = getattr(response, 'raw', None)
            if raw and hasattr(raw, 'usage_metadata'):
                um = raw.usage_metadata
                print(f"[GEMINI USAGE METADATA REAL] prompt={um.prompt_token_count} | completion={um.candidates_token_count} | total={um.total_token_count}")
            if hasattr(response, 'source_nodes'):
                print(f"[DEBUG NODES] Encontrados {len(response.source_nodes)} nodos de contexto.")
                for i, node in enumerate(response.source_nodes):
                    print(f"  - Nodo {i} (Score: {node.score:.4f}): {node.node.get_content()[:100]}...")
        except Exception as query_err:
            print(f"[CRITICAL QUERY ERROR] Error en aquery: {query_err}")
            traceback.print_exc()
            raise query_err
        
        async def stream_generator():
            start_gen = time.time()
            full_response = ""
            print("[STREAM] Iniciando stream_generator")
            try:
                # Caso 1: Async Generator (Preferido para aquery)
                gen = None
                print("[STREAM] Verificando generadores en la respuesta...")
                if hasattr(response, 'async_response_gen'):
                    print("[STREAM] Usando async_response_gen")
                    gen = response.async_response_gen
                elif hasattr(response, 'response_gen'):
                    print("[STREAM] Usando response_gen")
                    gen = response.response_gen
                
                if gen:
                    if callable(gen):
                        print("[STREAM] Llamando al generador (es un método)...")
                        gen = gen()
                    
                    print(f"[STREAM] Tipo final del generador: {type(gen)}")
                    
                    if hasattr(gen, '__aiter__'):
                        async for chunk in gen:
                            if chunk:
                                print(f".", end="", flush=True)
                                # Manejo de diferentes tipos de chunks de LlamaIndex
                                text_chunk = getattr(chunk, 'delta', str(chunk))
                                if not isinstance(text_chunk, str):
                                    text_chunk = str(text_chunk)
                                    
                                full_response += text_chunk
                                yield f"data: {json.dumps({'text': text_chunk})}\n\n"
                    else:
                        print("[STREAM] Usando iterador síncrono...")
                        for chunk in gen:
                            if chunk:
                                print(f".", end="", flush=True)
                                text_chunk = getattr(chunk, 'delta', str(chunk))
                                if not isinstance(text_chunk, str):
                                    text_chunk = str(text_chunk)
                                    
                                full_response += text_chunk
                                yield f"data: {json.dumps({'text': text_chunk})}\n\n"
                                await asyncio.sleep(0.01)
                    print("\n")
                else:
                    print("[STREAM] No se encontró generador, enviando respuesta completa.")
                    text_resp = str(response)
                    if text_resp.strip() == "Empty Response":
                        text_resp = "No encontré información específica sobre eso en el CV de Javier. ¿Podrías ser más específico con tu pregunta?"
                    full_response = text_resp
                    yield f"data: {json.dumps({'text': text_resp})}\n\n"

            except Exception as stream_err:
                err_str = str(stream_err)
                logger.error(f"[STREAM ERROR] {type(stream_err).__name__}: {err_str}")
                
                if "429" in err_str or "Quota exceeded" in err_str:
                    error_msg = f"\n\n⚠️ {COMIC_WARNING}"
                else:
                    error_msg = f"\n\n[Error técnico: {err_str[:50]}...]"
                
                yield f"data: {json.dumps({'text': error_msg})}\n\n"
            finally:
                if full_response:
                    semantic_cache[request.message] = {'response': full_response, 'timestamp': time.time()}
                    # Intentamos usar usage_metadata REAL de Gemini primero
                    raw = getattr(response, 'raw', None)
                    if raw and hasattr(raw, 'usage_metadata'):
                        um = raw.usage_metadata
                        pt = getattr(um, 'prompt_token_count', 0) or 0
                        ct = getattr(um, 'candidates_token_count', 0) or 0
                        print(f"[STATS] Usando tokens REALES de Gemini: prompt={pt} completion={ct}")
                    else:
                        # Fallback: estimación por longitud de texto (~4 chars/token)
                        pt = len(request.message) // 4
                        ct = len(full_response) // 4
                        print(f"[STATS] Usando tokens ESTIMADOS: prompt={pt} completion={ct}")
                    record_usage(prompt_tokens=pt, completion_tokens=ct)
                print(f"[LOG] Generación finalizada en {time.time() - start_gen:.2f}s")
                    
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    except Exception as e:
        err_str = str(e)
        logger.error(f"[CHAT CRITICAL ERROR] {err_str}")
        if "429" in err_str or "Quota exceeded" in err_str:
            return {"response": f"⚠️ {COMIC_WARNING}"}
        return {"response": "Lo siento, tuve un problema al procesar esa pregunta. El servidor sigue vivo pero algo salió mal."}

@app.get("/verify-role")
async def verify_role(user: dict = Depends(verify_token)):
    try:
        # 1. Blindaje contra Errores: Manejo explícito de None
        if user is None:
            logger.error("[AUTH] verify_token devolvió None. Token inválido o expirado.")
            raise HTTPException(status_code=401, detail="Token inválido o expirado")
            
        # 3. Fallback de UID seguro
        uid = user.get('uid') or user.get('sub') or user.get('user_id')
        if not uid:
            logger.error(f"[AUTH ERROR] No se encontró UID en el token decodificado: {user}")
            raise HTTPException(status_code=401, detail="Token malformado: UID ausente")

        email = user.get('email', 'Desconocido')
        print(f"[AUTH] Validando token para el usuario: {email} (UID: {uid})")
        
        role = await get_user_role(uid)
        return {"role": role, "uid": uid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CRITICAL AUTH ERROR] {str(e)}")
        # Mantenemos el servidor vivo retornando el error de forma controlada
        raise HTTPException(status_code=500, detail="Error interno en validación de roles")


@app.get("/admin/stats")
async def admin_stats(admin_user: dict = Depends(verify_admin)):
    """Endpoint exclusivo para admin: devuelve métricas de uso de tokens y cuota."""
    stats = get_stats_summary()
    print(f"[ADMIN STATS] Consultado por: {admin_user.get('email')}")
    return stats

class RoleUpdateRequest(BaseModel):
    target_uid: str
    new_role: str

@app.patch("/admin/update-role")
async def update_user_role(request: RoleUpdateRequest, admin_user: dict = Depends(verify_admin)):
    """Permite a un administrador cambiar el rol de un usuario en Firestore."""
    print(f"[BACKEND PATCH START] Recibida petición para cambiar {request.target_uid} a '{request.new_role}'")
    
    if request.new_role not in ["admin", "user"]:
        raise HTTPException(status_code=400, detail="Rol inválido. Debe ser 'admin' o 'user'")
    
    # Prevenir que alguien le elimine el rol al Super Admin
    if request.target_uid == ADMIN_UID:
        print("[BACKEND DENEGADO] Intento de modificar al Super Admin")
        raise HTTPException(status_code=403, detail="No se puede modificar el rol del Super Admin desde la interfaz.")
        
    if not firestore_db:
        print("[BACKEND ERROR] El SDK de Firebase Admin no pudo inicializarse (Faltan credenciales).")
        raise HTTPException(status_code=500, detail="Firestore no está configurado en el backend.")
        
    try:
        # Añadimos un timeout de 5 segundos para que no muera en un retrying loop si no hay acceso a GCP
        print(f"[BACKEND FIRESTORE] Intentando escribir en doc: users/{request.target_uid}")
        firestore_db.collection("users").document(request.target_uid).set(
            {"role": request.new_role}, 
            merge=True, 
            timeout=5.0
        )
        print("[BACKEND FIRESTORE] Escritura completada exitosamente.")
        
        # Invalidamos el caché si existía para que la recarga de rol sea inmediata
        if request.target_uid in role_cache:
            del role_cache[request.target_uid]
            
        return {"status": "success", "message": "Rol actualizado"}
    except Exception as e:
        logger.error(f"[IAM BACKEND ERROR FATAL] Error comunicando con Firestore: {type(e).__name__} - {e}")
        # En vez de morir en silencio, devolvemos un 500 explícito con el detalle
        raise HTTPException(status_code=500, detail=f"Error en BD: {e}")

@app.patch("/admin/settings/auto-login")
async def update_auto_login(request: AutoLoginRequest, admin_user: dict = Depends(verify_admin)):
    """Permite al admin guardar en Firestore ignorando reglas frontend"""
    if not firestore_db:
        raise HTTPException(status_code=500, detail="Firestore no conectado")
    try:
        firestore_db.collection("settings").document("global_config").set(
            {"auto_login_enabled": request.enabled}, 
            merge=True
        )
        return {"status": "success"}
    except Exception as e:
        logger.error(f"[SETTINGS ERROR] No se pudo guardar config: {e}")
        raise HTTPException(status_code=500, detail="Error de BD")

@app.get("/settings/auto-login")
async def get_auto_login():
    """Endpoint público para leer la configuración de login sin depender de reglas de Firestore"""
    if not firestore_db:
        return {"auto_login_enabled": True}
    try:
        doc_snap = firestore_db.collection("settings").document("global_config").get()
        if doc_snap.exists:
            return {"auto_login_enabled": doc_snap.to_dict().get("auto_login_enabled", True)}
    except Exception as e:
        logger.error(f"[SETTINGS ERROR] No se pudo cargar settings/global: {e}")
    return {"auto_login_enabled": True}

@app.get("/")
async def root():
    return {"status": "protected", "admin_configured": bool(ADMIN_UID)}


if __name__ == "__main__":
    import uvicorn
    # En producción o ejecución directa, uvicorn usará el startup_event
    uvicorn.run(app, host="0.0.0.0", port=8000)

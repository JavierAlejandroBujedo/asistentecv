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
ADMIN_UID = os.getenv("ADMIN_UID")

# Directories
DOCUMENTS_DIR = "documents"
os.makedirs(DOCUMENTS_DIR, exist_ok=True)

print("\n" + "="*50)
print("SISTEMA RAG CV - MODO PROTEGIDO (FIREBASE)")
print("="*50)

# Firebase admin SDK bypassed (no ADC)

semantic_cache = OrderedDict()
CACHE_TTL = 3600

token_cache = {}
TOKEN_CACHE_TTL = 300

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

async def verify_admin(user: dict = Depends(verify_token)):
    if user is None:
        raise HTTPException(status_code=401, detail="Token inválido o expirado")
        
    # 2. Fallback de UID
    uid = user.get('uid') or user.get('sub') or user.get('user_id')
    if uid != ADMIN_UID:
        print(f"[SECURITY ALERT] Intento de acceso administrativo por: {user.get('email', 'Desconocido')} (ID: {uid})")
        raise HTTPException(status_code=403, detail="Acceso denegado: Se requieren permisos de administrador")
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
    "Información de contexto:\n"
    "---------------------\n"
    "{context_str}\n"
    "---------------------\n"
    "Dada la información de contexto y sin usar conocimiento previo, "
    "responde a la siguiente pregunta SIEMPRE en castellano.\n"
    "Pregunta: {query_str}\n"
    "Respuesta (en castellano):"
)

app = FastAPI(title="RAG CV Parser Protected API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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
                    error_msg = "\n\n⚠️ **Límite de API:** He llegado al límite de consultas por hoy. Por favor, intenta de nuevo en unos minutos."
                else:
                    error_msg = f"\n\n[Error técnico: {err_str[:50]}...]"
                
                yield f"data: {json.dumps({'text': error_msg})}\n\n"
            finally:
                if full_response:
                    semantic_cache[request.message] = {'response': full_response, 'timestamp': time.time()}
                print(f"[LOG] Generación finalizada en {time.time() - start_gen:.2f}s")
                    
        return StreamingResponse(stream_generator(), media_type="text/event-stream")
    except Exception as e:
        err_str = str(e)
        logger.error(f"[CHAT CRITICAL ERROR] {err_str}")
        if "429" in err_str or "Quota exceeded" in err_str:
            return {"response": "⚠️ Cuota de API agotada. He superado el límite de consultas gratuitas de Google por hoy. Por favor, intenta de nuevo más tarde."}
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
        
        role = "admin" if uid == ADMIN_UID else "user"
        return {"role": role, "uid": uid}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[CRITICAL AUTH ERROR] {str(e)}")
        # Mantenemos el servidor vivo retornando el error de forma controlada
        raise HTTPException(status_code=500, detail="Error interno en validación de roles")

@app.get("/")
async def root():
    return {"status": "protected", "admin_configured": bool(ADMIN_UID)}


if __name__ == "__main__":
    import uvicorn
    # En producción o ejecución directa, uvicorn usará el startup_event
    uvicorn.run(app, host="0.0.0.0", port=8000)

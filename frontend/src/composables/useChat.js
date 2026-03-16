import { ref } from 'vue';
import { APP_CONFIG } from '../config';
import { auth, db, collection, addDoc, serverTimestamp, query, where, orderBy, onSnapshot } from '../firebase';

// Flag para mostrar el mensaje de "leyendo calidad" solo la primera vez
// v1.0.3 - Fixed repetitive placeholder
let hasShownFirstWaitMessage = false;

const history = ref([]);
const loading = ref(false);
const isOffline = ref(!navigator.onLine);
const historyRecords = ref([]);
let unsubscribeHistory = null;

/**
 * Composable to handle Chat Logic and History
 * @returns {Object} Chat state and methods
 */
export function useChat() {
    // Monitorización de conexión
    const updateOnlineStatus = () => {
        isOffline.value = !navigator.onLine;
        if (isOffline.value) {
            window.dispatchEvent(new CustomEvent('custom-offline', {
                detail: {
                    title: '¡Alerta!',
                    message: 'Parece que el cable del internet se fue de vacaciones.'
                }
            }));
        }
    };

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);

    /**
     * Sends a message to the AI backend and logs to Firestore
     * @param {string} messageText 
     */
    const sendMessage = async (messageText) => {
        if (!messageText.trim() || loading.value) return;

        loading.value = true;

        // Mensaje de espera simplificado
        const waitMessage = "Generando respuesta...";


        history.value.push({
            text: messageText,
            response: waitMessage // Se mostrará este texto inicial
        });
        const currentMessageIndex = history.value.length - 1;

        let finalResponse = "";
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), 30000); // 30s timeout

        try {
            // 1. Obtención del token de Firebase
            let token = null;
            if (auth.currentUser) {
                token = await auth.currentUser.getIdToken(true);
            }

            console.log(`[CHAT DEBUG] Enviando mensaje. Token: ${token ? 'OK' : 'MISSING'}`);

            const reqHeaders = { 'Content-Type': 'application/json' };
            if (token) {
                reqHeaders['Authorization'] = `Bearer ${token}`;
            }

            const res = await fetch(`${APP_CONFIG.API_BASE_URL}/chat`, {
                method: 'POST',
                headers: reqHeaders,
                body: JSON.stringify({ message: messageText }),
                signal: controller.signal
            });

            clearTimeout(timeoutId);

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(errorData.detail || `Error del servidor: ${res.status}`);
            }

            const contentType = res.headers.get("content-type");

            // 2. Procesar respuesta según el tipo (JSON o Stream)
            if (contentType && contentType.includes("application/json")) {
                const jsonRes = await res.json();
                finalResponse = jsonRes.response || jsonRes.message || "Sin respuesta legible.";
                history.value[currentMessageIndex].response = finalResponse;
            } else {
                const reader = res.body.getReader();
                const decoder = new TextDecoder("utf-8");
                let buffer = "";

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;

                    buffer += decoder.decode(value, { stream: true });
                    const parts = buffer.split('\n\n');
                    buffer = parts.pop();

                    for (const part of parts) {
                        const line = part.trim();
                        if (line.startsWith('data: ')) {
                            try {
                                const jsonData = JSON.parse(line.substring(6));
                                if (jsonData.text) {
                                    // Limpiar el mensaje de espera inicial al recibir el primer token real
                                    if (!finalResponse) finalResponse = "";
                                    finalResponse += jsonData.text;
                                    history.value[currentMessageIndex].response = finalResponse;
                                }
                            } catch (e) {
                                console.warn("Error parseando stream chunk:", e);
                            }
                        }
                    }
                }

                // Si terminó el stream y no hay respuesta (ej. error 429 capturado en backend pero no enviado en data)
                if (!finalResponse) {
                    finalResponse = "El cerebro de Javier está descansando (Límite de API superado). Por favor, intenta de nuevo en unos momentos.";
                    history.value[currentMessageIndex].response = finalResponse;
                }
            }

            // 3. Registrar en auditoría si se obtuvo respuesta
            if (finalResponse) {
                await addDoc(collection(db, "chat_history"), {
                    userId: auth.currentUser?.uid || 'anonymous',
                    userName: auth.currentUser?.displayName || 'Anónimo',
                    userEmail: auth.currentUser?.email || 'Sin identificar',
                    prompt: messageText,
                    response: finalResponse,
                    timestamp: serverTimestamp()
                });
            }

        } catch (err) {
            console.error("Chat error:", err);
            finalResponse = `Lo siento: ${err.message}`;
            history.value[currentMessageIndex].response = finalResponse;
        } finally {
            loading.value = false;
            clearTimeout(timeoutId);
        }
    };

    const clearChat = () => {
        history.value = [];
    };

    const loadHistoryItem = (record) => {
        history.value = [{ text: record.prompt, response: record.response }];
    };

    const setupHistoryListener = (uid) => {
        if (unsubscribeHistory) unsubscribeHistory();
        if (!uid) {
            historyRecords.value = [];
            return;
        }

        const q = query(
            collection(db, "chat_history"),
            where("userId", "==", uid),
            orderBy("timestamp", "desc")
        );

        unsubscribeHistory = onSnapshot(q, (snapshot) => {
            historyRecords.value = snapshot.docs.map(doc => ({
                id: doc.id,
                ...doc.data()
            }));
        });
    };

    return {
        history,
        loading,
        isOffline,
        historyRecords,
        sendMessage,
        clearChat,
        loadHistoryItem,
        setupHistoryListener
    };
}

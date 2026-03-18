// Configuración Centralizada de la App
const isLocalhost = window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1";

export const APP_CONFIG = {
    API_BASE_URL: isLocalhost ? "http://localhost:8000" : "https://asistentecv.onrender.com"
};

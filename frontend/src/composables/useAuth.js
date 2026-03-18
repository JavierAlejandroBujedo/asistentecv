import { ref, computed, onMounted } from 'vue';
import { auth, db, googleProvider, signInWithPopup, signOut, onAuthStateChanged, doc, setDoc, serverTimestamp } from '../firebase';
import axios from 'axios';
import { APP_CONFIG } from '../config';



// Axios Interceptor for Firebase Token
axios.interceptors.request.use(async (config) => {
    const currentUser = auth.currentUser;
    if (currentUser) {
        const token = await currentUser.getIdToken();
        config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
}, (error) => {
    return Promise.reject(error);
});

const user = ref(null);
const userRole = ref(null);
const loading = ref(false);
const isAuthReady = ref(false); // true cuando Firebase resolvió la sesión persistida

/**
 * Composable to handle Authentication and User Synchronization
 * @returns {Object} User state and auth methods
 */
export function useAuth() {
    const isAdmin = computed(() => user.value && userRole.value === 'admin');

    let lastUidVerified = null;

    /**
     * Verifies the user role through the backend API
     * @param {Object} firebaseUser 
     */
    const fetchRole = async (firebaseUser) => {
        // 3. Optimización: Evitar peticiones infinitas si el UID no cambió
        if (firebaseUser.uid === lastUidVerified && userRole.value) {
            return;
        }

        loading.value = true;
        try {
            const token = await firebaseUser.getIdToken();
            const response = await axios.get(`${APP_CONFIG.API_BASE_URL}/verify-role`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            userRole.value = response.data.role;
            lastUidVerified = firebaseUser.uid;
            console.log(`%c[Auth] 🛡️ Rol verificado: ${userRole.value}`, 'color: #34a853; font-weight: bold;');
        } catch (e) {
            console.error("Error verifying role on server:", e);
            // 2. Interceptores de Frontend: Detectar caída del servidor
            const isConnectionError = !navigator.onLine || e.message === "Network Error" || e.code === "ERR_NETWORK";
            if (isConnectionError) {
                console.warn("¡Alerta roja! El servidor se ha tomado un descanso no programado.");
                window.dispatchEvent(new CustomEvent('custom-offline', {
                    detail: {
                        title: '¡Alerta!',
                        message: 'Parece que el cable del internet se fue de vacaciones. Mientras tanto, puedes hablar con la pared, aunque responde menos que mi IA sin señal.'
                    }
                }));
            }
            userRole.value = "user"; // Fallback
            lastUidVerified = null;
        } finally {
            loading.value = false;
        }
    };

    /**
     * Synchronizes user data with Firestore 'users' collection
     * @param {Object} firebaseUser 
     */
    const syncUserToFirestore = async (firebaseUser) => {
        try {
            const userRef = doc(db, "users", firebaseUser.uid);
            const userData = {
                displayName: firebaseUser.displayName,
                email: firebaseUser.email,
                photoURL: firebaseUser.photoURL,
                lastLogin: serverTimestamp(),
            };
            if (userRole.value) userData.role = userRole.value;
            await setDoc(userRef, userData, { merge: true });
            console.log('%c[Firestore] ✅ Datos de usuario sincronizados.', 'color: #34a853;');
        } catch (e) {
            // permission-denied es esperado para usuarios normales sin regla de escritura propia
            if (e.code === 'permission-denied') return;
            console.error('[Firestore] Error sincronizando usuario:', e);
        }
    };

    const handleLogin = async () => {
        loading.value = true;
        console.log(`%c[Auth] 🚀 Intentando conexión con Google...`, 'color: #4285f4; font-weight: bold;');
        console.log(`%c[Auth] 🌐 Puerto detectado: ${window.location.port || '80'}`, 'color: #4285f4;');
        try {
            await signInWithPopup(auth, googleProvider);
        } catch (e) {
            console.error("[Auth] ❌ Login fallido:", e.code, e.message);
        } finally {
            loading.value = false;
        }
    };

    const handleLogout = async () => {
        try {
            await signOut(auth);
            userRole.value = null;
        } catch (e) {
            console.error("Logout failed:", e);
        }
    };

    // Global listener setup — se dispara UNA vez al cargar (con sesión cacheada) o null si no hay sesión
    onAuthStateChanged(auth, async (firebaseUser) => {
        user.value = firebaseUser;
        if (firebaseUser) {
            await fetchRole(firebaseUser);
            await syncUserToFirestore(firebaseUser);
        } else {
            lastUidVerified = null;
            userRole.value = null;
        }
        // Marcamos que Firebase ya resolvió el estado inicial (con o sin usuario)
        isAuthReady.value = true;
    });

    return {
        user,
        userRole,
        isAdmin,
        isAuthReady,
        loading,
        handleLogin,
        handleLogout
    };
}

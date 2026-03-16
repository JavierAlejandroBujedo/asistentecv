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

        try {
            // Aseguramos de enviar el token explícitamente ya que auth.currentUser podría estar desincronizado en este primer ciclo
            const token = await firebaseUser.getIdToken();
            const response = await axios.get(`${APP_CONFIG.API_BASE_URL}/verify-role`, {
                headers: { Authorization: `Bearer ${token}` }
            });
            userRole.value = response.data.role;
            lastUidVerified = firebaseUser.uid;
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
        } catch (e) {
            console.error("Error syncing user to Firestore:", e);
        }
    };

    const handleLogin = async () => {
        loading.value = true;
        try {
            await signInWithPopup(auth, googleProvider);
        } catch (e) {
            console.error("Login failed:", e);
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

    // Global listener setup
    onAuthStateChanged(auth, async (firebaseUser) => {
        user.value = firebaseUser;
        if (firebaseUser) {
            await fetchRole(firebaseUser);
            await syncUserToFirestore(firebaseUser);
        } else {
            lastUidVerified = null;
            userRole.value = null;
        }
    });

    return {
        user,
        userRole,
        isAdmin,
        loading,
        handleLogin,
        handleLogout
    };
}

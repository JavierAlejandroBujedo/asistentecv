import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup, signInWithRedirect, signOut, onAuthStateChanged, setPersistence, browserLocalPersistence } from "firebase/auth";
import { getFirestore, collection, addDoc, query, where, orderBy, onSnapshot, serverTimestamp, doc, setDoc, deleteDoc } from "firebase/firestore";

const firebaseConfig = {
    apiKey: "AIzaSyCzJJUsZXn6sDeW9KJyVFpr_FTzwe6KHxU",
    authDomain: "cvjavieralejandrobujedo.firebaseapp.com",
    projectId: "cvjavieralejandrobujedo",
    storageBucket: "cvjavieralejandrobujedo.firebasestorage.app",
    messagingSenderId: "568323437996",
    appId: "1:568323437996:web:7b7a8ceddd5234140ff609"
};

console.log(`%c[Firebase] 🔥 Inicializando app en ${window.location.origin}...`, 'color: #f59e0b; font-weight: bold;');

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
const db = getFirestore(app);
const googleProvider = new GoogleAuthProvider();
googleProvider.setCustomParameters({ prompt: 'select_account' });

// Configurar persistencia local (Token guardado en el navegador)
setPersistence(auth, browserLocalPersistence)
    .then(() => console.log('%c[Firebase Auth] ✅ Persistencia local configurada correctamente.', 'color: #34a853; font-weight: bold;'))
    .catch((error) => console.error('[Firebase Auth] ❌ Error configurando persistencia:', error));

// Diagnóstico del estado de autenticación
onAuthStateChanged(auth, (firebaseUser) => {
    if (firebaseUser) {
        console.log(`%c[Auth] ✅ Usuario detectado: ${firebaseUser.email} (UID: ${firebaseUser.uid})`, 'color: #34a853; font-weight:bold;');
    } else {
        console.log('%c[Auth] 🔓 Sin sesión activa. Esperando login...', 'color: #9ca3af;');
    }
});

export {
    auth, db, googleProvider, signInWithPopup, signInWithRedirect, signOut, onAuthStateChanged,
    collection, addDoc, query, where, orderBy, onSnapshot, serverTimestamp, doc, setDoc, deleteDoc
};

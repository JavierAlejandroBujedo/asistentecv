import { initializeApp } from "firebase/app";
import { getAuth, GoogleAuthProvider, signInWithPopup, signOut, onAuthStateChanged, setPersistence, browserLocalPersistence } from "firebase/auth";
import { getFirestore, collection, addDoc, query, where, orderBy, onSnapshot, serverTimestamp, doc, setDoc, deleteDoc } from "firebase/firestore";

const firebaseConfig = {
    apiKey: "AIzaSyCzJJUsZXn6sDeW9KJyVFpr_FTzwe6KHxU",
    authDomain: "cvjavieralejandrobujedo.firebaseapp.com",
    projectId: "cvjavieralejandrobujedo",
    storageBucket: "cvjavieralejandrobujedo.firebasestorage.app",
    messagingSenderId: "568323437996",
    appId: "1:568323437996:web:7b7a8ceddd5234140ff609"
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);

// Configurar persistencia local (Token guardado en el navegador)
setPersistence(auth, browserLocalPersistence)
    .catch((error) => console.error("Error configurando persistencia:", error));

const db = getFirestore(app);
const googleProvider = new GoogleAuthProvider();

export {
    auth, db, googleProvider, signInWithPopup, signOut, onAuthStateChanged,
    collection, addDoc, query, where, orderBy, onSnapshot, serverTimestamp, doc, setDoc, deleteDoc
};

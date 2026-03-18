<template>
  <v-app theme="dark" class="bg-black">

    <!-- === PANTALLA DE CARGA: Mientras Firebase resuelve la sesión cacheada === -->
    <transition name="auth-fade">
      <div v-if="!isAuthReady" class="auth-loading-screen">
        <div class="auth-loader-content">
          <v-progress-circular indeterminate color="#4285f4" size="48" width="3" />
        </div>
      </div>
    </transition>

    <!-- === APP REAL: Solo se muestra cuando Firebase ya resolvió === -->
    <template v-if="isAuthReady">
      <!-- Sidebar Modular -->
      <ChatSidebar 
        ref="sidebarRef" 
        @new-chat="handleNewChat" 
        @load-history="handleHistoryLoad" 
      />

      <v-app-bar app elevation="0" color="black" class="px-2">

        <!-- Hamburguesa: solo mobile -->
        <v-btn
          v-if="mobile"
          icon="mdi-menu"
          variant="text"
          color="grey-lighten-1"
          class="ml-1"
          @click="sidebarRef?.toggleDrawer()"
        ></v-btn>

        <!-- Título -->
        <v-toolbar-title
          :class="[
            'text-grey-lighten-1 font-weight-black letter-spacing-1',
            mobile ? '' : 'ml-15 pl-2'
          ]"
        >
          ChatCV
        </v-toolbar-title>

        <!-- Botones de Modo para Admin (visible siempre para admin) -->
        <v-btn-toggle v-if="isAdmin" v-model="tab" mandatory theme="dark" variant="text" color="#a78bfa" class="mx-auto overflow-x-auto" style="white-space: nowrap;">
          <v-btn value="users" class="text-none">Usuarios</v-btn>
          <v-btn value="audit" class="text-none">Auditoría</v-btn>
          <v-btn v-if="!mobile" value="chat" class="text-none">Chat</v-btn>
          <v-btn value="upload" class="text-none">CV</v-btn>
          <v-btn value="stats" class="text-none">
            <v-icon size="16" class="mr-1">mdi-chart-timeline-variant-shimmer</v-icon>
            Estadísticas
          </v-btn>
        </v-btn-toggle>

        <template v-slot:append>
          <!-- Login Button — Mobile (solo ícono centrado) -->
          <v-btn
            v-if="!user && mobile"
            variant="flat"
            color="#4285f4"
            class="rounded-lg mr-2 pa-0"
            min-width="40"
            width="40"
            height="40"
            @click="handleLogin"
            :loading="loading"
          >
            <v-img src="/src/assets/google_icon.png" width="20" height="20" class="bg-white rounded-circle pa-1"></v-img>
          </v-btn>

          <!-- Login Button — Desktop (con texto) -->
          <v-btn
            v-else-if="!user"
            variant="flat"
            color="#4285f4"
            class="rounded-lg text-none px-4 mr-2 font-weight-bold"
            @click="handleLogin"
            :loading="loading"
          >
            <template v-slot:prepend>
              <v-img src="/src/assets/google_icon.png" width="20" height="20" class="mr-1 bg-white rounded-circle pa-1"></v-img>
            </template>
            ACCEDER
          </v-btn>

          <!-- Profile Menu -->
          <v-menu v-else location="bottom end" transition="slide-y-transition">
            <template v-slot:activator="{ props }">
              <v-avatar v-bind="props" size="36" class="mr-4 cursor-pointer border-grey-lite">
                <v-img :src="user.photoURL"></v-img>
              </v-avatar>
            </template>
            <v-list bg-color="#1e1f20" class="rounded-lg border-grey-lite mt-2" width="180">
              <v-list-item v-if="isAdmin" @click="tab = 'users'" prepend-icon="mdi-view-dashboard-outline" title="Panel" class="text-grey-lighten-2 py-3"></v-list-item>
              <v-list-item v-else @click="openEmail" prepend-icon="mdi-email-outline" title="Contactar" class="text-grey-lighten-2 py-3"></v-list-item>
              <v-divider color="grey-darken-3"></v-divider>
              <v-list-item @click="handleLogout" prepend-icon="mdi-logout" title="Salir" color="error" class="py-3"></v-list-item>
            </v-list>
          </v-menu>
        </template>
      </v-app-bar>

      <v-main class="pa-0">
        <v-window v-model="tab" class="fill-height">
          <v-window-item value="chat" class="fill-height">
            <ChatWindow />
          </v-window-item>
          
          <v-window-item value="users" v-if="isAdmin" class="fill-height">
            <UsersGrid />
          </v-window-item>
          
          <v-window-item value="audit" v-if="isAdmin" class="fill-height">
            <AuditGrid />
          </v-window-item>
          
          <v-window-item value="upload" v-if="isAdmin" class="fill-height">
            <UploadCV />
          </v-window-item>

          <v-window-item value="stats" v-if="isAdmin" class="fill-height">
            <keep-alive>
              <StatsDashboard />
            </keep-alive>
          </v-window-item>

        </v-window>
      </v-main>

      <!-- Offline Alert Modular -->
      <OfflineAlert />
    </template>

  </v-app>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue';
import { useDisplay } from 'vuetify';
import { useAuth } from './composables/useAuth';
import { useChat } from './composables/useChat';
import { auth, db, doc, onSnapshot } from './firebase';
import { APP_CONFIG } from './config';

// Components
import ChatSidebar from './components/ChatSidebar.vue';
import ChatWindow from './components/ChatWindow.vue';
import UsersGrid from './components/UsersGrid.vue';
import AuditGrid from './components/AuditGrid.vue';
import UploadCV from './components/UploadCV.vue';
import OfflineAlert from './components/OfflineAlert.vue';
import StatsDashboard from './components/StatsDashboard.vue';

const { mobile } = useDisplay();
const tab = ref('chat');
const sidebarRef = ref(null);
const { user, isAdmin, isAuthReady, loading, handleLogin, handleLogout } = useAuth();
const { clearChat, loadHistoryItem, setupHistoryListener } = useChat();

// Control del Auto-Login Prompt
const autoLoginEnabled = ref(true);

// Auto-login logic (10s delay)
let countdownInterval = null;

const startLoginTimer = () => {
    if (countdownInterval) clearInterval(countdownInterval);
    if (!autoLoginEnabled.value || user.value) return; // Si el admin lo apagó o ya está logueado, abortar
    
    let timeLeft = 10;
    countdownInterval = setInterval(() => {
        timeLeft--;
        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            if (!user.value && autoLoginEnabled.value) handleLogin();
        }
    }, 1000);
};

const handleNewChat = () => {
    clearChat();
    tab.value = 'chat';
    if (mobile.value) sidebarRef.value?.toggleDrawer();
};

const handleHistoryLoad = (item) => {
    loadHistoryItem(item);
    tab.value = 'chat';
    if (mobile.value) sidebarRef.value?.toggleDrawer();
};

const openEmail = () => {
    window.location.href = "mailto:javieralejandrobujedo022@gmail.com";
};

// Sync history listener with user status
watch(user, (newUser) => {
  if (newUser) {
    setupHistoryListener(newUser.uid);
  } else {
    setupHistoryListener(null);
    clearChat(); // Limpia la pantalla de chat
    tab.value = 'chat'; // Regresa a la pestaña principal
  }
}, { immediate: true });

// El contador de auto-login solo arranca cuando Firebase confirmó que NO hay sesión activa
watch(isAuthReady, (ready) => {
  if (ready && !user.value && autoLoginEnabled.value) {
    startLoginTimer();
  }
});

onMounted(async () => {
    // 1. Carga inicial Vía Backend (Bypass de Firestore Rules) para invitados limpios
    try {
        const res = await fetch(`${APP_CONFIG.API_BASE_URL}/settings/auto-login`);
        if (res.ok) {
            const data = await res.json();
            autoLoginEnabled.value = data.auto_login_enabled ?? true;
        }
    } catch (e) {
        // Silencioso: el backend puede no estar disponible en este momento (modo offline o Render en frío)
        console.debug('[App] Settings de auto-login no disponibles, usando valor por defecto.');
    }
    
    // Si la configuración sigue activa después de la carga segura, iniciar temporizador
    if (!user.value && autoLoginEnabled.value) startLoginTimer();

    // 2. Listener en Tiempo Real para Administradores —  solo si hay sesión activa
    if (auth.currentUser) {
      const unsubscribeLocal = onSnapshot(doc(db, "settings", "global_config"), (docSnap) => {
          if (docSnap.exists()) {
              autoLoginEnabled.value = docSnap.data().auto_login_enabled ?? true;
              if (!autoLoginEnabled.value && countdownInterval) {
                  clearInterval(countdownInterval);
              } else if (autoLoginEnabled.value && !user.value && !countdownInterval) {
                  startLoginTimer();
              }
          }
      }, (error) => {
          console.debug('[App] Listener de settings ignorado: sin permisos de lectura.');
      });
    }
});
</script>

<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

html, body {
  background-color: #000000 !important;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

.v-application {
  font-family: 'Inter', sans-serif !important;
}

.border-grey-lite {
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

.cursor-pointer { cursor: pointer; }
.letter-spacing-1 { letter-spacing: 0.1em; }

/* === Auth Loading Screen === */
.auth-loading-screen {
  position: fixed;
  inset: 0;
  z-index: 9999;
  background: #000000;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-loader-content {
  display: flex;
  flex-direction: column;
  align-items: center;
}

/* Transición suave al desaparecer */
.auth-fade-leave-active {
  transition: opacity 0.4s ease;
}
.auth-fade-leave-to {
  opacity: 0;
}

html, body {
  background-color: #000000 !important;
  margin: 0;
  padding: 0;
  overflow: hidden;
}

.v-application {
  font-family: 'Inter', sans-serif !important;
}

.border-grey-lite {
  border: 1px solid rgba(255, 255, 255, 0.1) !important;
}

.cursor-pointer { cursor: pointer; }
.letter-spacing-1 { letter-spacing: 0.1em; }

/* Hide global scrollbars */
* {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
}
*::-webkit-scrollbar {
  display: none !important;
}
</style>

<template>
  <v-app theme="dark" class="bg-black">
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
      <v-btn-toggle v-if="isAdmin" v-model="tab" mandatory theme="dark" variant="text" color="#4285f4" class="mx-auto overflow-x-auto" style="white-space: nowrap;">
        <v-btn value="audit" class="text-none">Usuario</v-btn>
        <v-btn v-if="!mobile" value="chat" class="text-none">Probar Chat</v-btn>
        <v-btn value="upload" class="text-none">CV</v-btn>
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
            <v-list-item v-if="isAdmin" @click="tab = 'audit'" prepend-icon="mdi-view-dashboard-outline" title="Panel" class="text-grey-lighten-2 py-3"></v-list-item>
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
        
        <v-window-item value="audit" v-if="isAdmin" class="fill-height">
          <AuditGrid />
        </v-window-item>
        
        <v-window-item value="upload" v-if="isAdmin" class="fill-height">
          <UploadCV />
        </v-window-item>
      </v-window>
    </v-main>

    <!-- Offline Alert Modular -->
    <OfflineAlert />
  </v-app>
</template>

<script setup>
import { ref, watch, onMounted } from 'vue';
import { useDisplay } from 'vuetify';
import { useAuth } from './composables/useAuth';
import { useChat } from './composables/useChat';

// Components
import ChatSidebar from './components/ChatSidebar.vue';
import ChatWindow from './components/ChatWindow.vue';
import AuditGrid from './components/AuditGrid.vue';
import UploadCV from './components/UploadCV.vue';
import OfflineAlert from './components/OfflineAlert.vue';

const { mobile } = useDisplay();
const tab = ref('chat');
const sidebarRef = ref(null);
const { user, isAdmin, loading, handleLogin, handleLogout } = useAuth();
const { clearChat, loadHistoryItem, setupHistoryListener } = useChat();

// Auto-login logic (10s delay)
let countdownInterval = null;
const startLoginTimer = () => {
    if (countdownInterval) clearInterval(countdownInterval);
    let timeLeft = 10;
    countdownInterval = setInterval(() => {
        timeLeft--;
        if (timeLeft <= 0) {
            clearInterval(countdownInterval);
            if (!user.value) handleLogin();
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
    startLoginTimer();
  }
}, { immediate: true });

onMounted(() => {
    if (!user.value) startLoginTimer();
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

/* Hide global scrollbars */
* {
  scrollbar-width: none !important;
  -ms-overflow-style: none !important;
}
*::-webkit-scrollbar {
  display: none !important;
}
</style>

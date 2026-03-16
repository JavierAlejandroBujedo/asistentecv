<template>
  <v-navigation-drawer
    app
    v-model="drawer"
    :rail="!mobile && rail"
    :temporary="mobile"
    :permanent="!mobile"
    :rail-width="64"
    width="238"
    color="#1e1f20"
    elevation="0"
    class="sidebar-drawer no-borders"
    :style="mobile ? 'background-color: #1e1f20 !important;' : ''"
  >
    <!-- Rail Header (Toggle) — solo en desktop -->
    <div v-if="!mobile" style="width: 64px; height: 64px;" class="d-flex align-center justify-center">
      <v-btn icon="mdi-menu" variant="text" color="grey-lighten-1" @click="rail = !rail"></v-btn>
    </div>

    <!-- Expanded content -->
    <div v-if="mobile || !rail" class="pa-4 pt-6 d-flex flex-column fill-height overflow-hidden">
      <!-- New Chat Button + flecha cerrar (mobile) -->
      <div class="d-flex align-center mb-6 px-2">
        <div class="d-flex align-center cursor-pointer new-chat-btn flex-grow-1" @click="$emit('new-chat')">
          <v-icon color="#4285f4" size="20" class="mr-3">mdi-plus</v-icon>
          <span class="text-subtitle-2 font-weight-bold">NUEVO CHAT</span>
        </div>
        <!-- Flecha para contraer — solo en mobile -->
        <v-btn
          v-if="mobile"
          icon="mdi-chevron-left"
          variant="text"
          color="grey-darken-1"
          size="small"
          class="ml-1"
          @click="drawer = false"
        ></v-btn>
      </div>

      <!-- History List -->
      <v-list bg-color="transparent" density="compact" class="flex-grow-1 overflow-y-auto px-0 custom-scrollbar">
        <template v-if="historyRecords.length > 0">
          <v-list-item
            v-for="record in historyRecords"
            :key="record.id"
            rounded="lg"
            class="mb-1 chat-item"
            @click="$emit('load-history', record)"
          >
            <v-list-item-title class="text-body-2 text-no-wrap text-grey-lighten-2">
              {{ truncateText(record.prompt) }}
            </v-list-item-title>
          </v-list-item>
        </template>
        <div v-else class="text-center pa-10 text-grey-darken-2 text-body-2 italic">
          Sin historial
        </div>
      </v-list>
      
      <!-- User Footer -->
      <v-list bg-color="transparent" density="compact" class="mb-4" v-if="user">
        <v-list-item @click="handleLogout" prepend-icon="mdi-logout" title="Salir" color="error" rounded="lg"></v-list-item>
      </v-list>
    </div>

    <!-- Rail Footer (User Profile) -->
    <template v-slot:append v-if="!mobile && rail && user">
      <div class="d-flex justify-center pb-6">
        <v-avatar size="32" class="cursor-pointer" @click="rail = false">
          <v-img :src="user.photoURL"></v-img>
        </v-avatar>
      </div>
    </template>
  </v-navigation-drawer>
</template>

<script setup>
import { ref, watch } from 'vue';
import { useDisplay } from 'vuetify';
import { useAuth } from '../composables/useAuth';
import { useChat } from '../composables/useChat';

const emit = defineEmits(['new-chat', 'load-history']);
const { mobile } = useDisplay();
const { user, handleLogout } = useAuth();
const { historyRecords } = useChat();

const drawer = ref(true);
const rail = ref(true);

// En mobile: drawer cerrado (se abre con el botón hamburguesa del app bar)
// En desktop: drawer visible en modo rail
watch(mobile, (isMobile) => {
  if (isMobile) {
    drawer.value = false;
    rail.value = false;
  } else {
    drawer.value = true;
    rail.value = true;
  }
}, { immediate: true });

const toggleDrawer = () => { drawer.value = !drawer.value; };

defineExpose({ toggleDrawer });

const truncateText = (text) => text?.length > 25 ? text.substring(0, 22) + '...' : text;
</script>

<style scoped>
.sidebar-drawer {
  border: none !important;
  transition: width 0.3s cubic-bezier(0.4, 0, 0.2, 1) !important;
}

.new-chat-btn {
  color: #4285f4;
  letter-spacing: 0.5px;
  transition: all 0.2s;
  padding: 8px;
  border-radius: 8px;
}

.new-chat-btn:hover {
  background: rgba(66, 133, 244, 0.1);
}

.chat-item {
  transition: background-color 0.2s;
}

.chat-item:hover {
  background-color: rgba(255, 255, 255, 0.05) !important;
}

.custom-scrollbar::-webkit-scrollbar {
  display: none;
}
</style>

<template>
  <v-fade-transition>
    <div v-if="offline" class="offline-overlay">
      <v-card class="pa-10 rounded-xl text-center bg-grey-darken-4 border-none shadow-none">
        <v-icon size="80" color="primary" class="mb-5">mdi-coffee</v-icon>
        <div class="text-h4 font-weight-black mb-4 white--text">{{ title }}</div>
        <p class="text-h6 text-grey-lighten-1">{{ message }}</p>
      </v-card>
    </div>
  </v-fade-transition>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';

const offline = ref(!navigator.onLine);
const title = ref('¡Ups! Estoy recargando café...');
const message = ref('Vuelvo cuando recuperes el internet ☕⚡');

const updateOnlineStatus = () => {
  offline.value = !navigator.onLine;
  if (!offline.value) {
    title.value = '¡Ups! Estoy recargando café...';
    message.value = 'Vuelvo cuando recuperes el internet ☕⚡';
  }
};

const handleCustomOffline = (e) => {
  if (e.detail?.title) title.value = e.detail.title;
  if (e.detail?.message) message.value = e.detail.message;
  offline.value = true;
};

onMounted(() => {
  window.addEventListener('online', updateOnlineStatus);
  window.addEventListener('offline', updateOnlineStatus);
  window.addEventListener('custom-offline', handleCustomOffline);
});

onUnmounted(() => {
  window.removeEventListener('online', updateOnlineStatus);
  window.removeEventListener('offline', updateOnlineStatus);
  window.removeEventListener('custom-offline', handleCustomOffline);
});
</script>

<style scoped>
.offline-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100vw;
  height: 100vh;
  background: rgba(0, 0, 0, 0.85);
  backdrop-filter: blur(10px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 99999;
}
</style>

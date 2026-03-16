<template>
  <v-dialog :model-value="!isOnline" persistent max-width="500">
    <v-card class="pa-6 text-center" color="surface" elevation="24">
      <v-icon size="80" color="warning" class="mb-4">mdi-wifi-off</v-icon>
      <h2 class="text-h4 mb-4 font-weight-bold">¡Houston, tenemos un problema!</h2>
      <p class="text-body-1 mb-6 text-grey-lighten-1">
        Parece que te has desconectado de la Matrix. 
        Ni siquiera mi IA superpoderosa puede alcanzarte sin internet. 
        <br><br>
        <strong>¿Has probado a soplar el router? A veces funciona...</strong>
      </p>
      <v-btn
        color="primary"
        size="large"
        block
        @click="checkConnection"
        prepend-icon="mdi-refresh"
      >
        Reintentar conexión
      </v-btn>
    </v-card>
  </v-dialog>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'

const isOnline = ref(navigator.onLine)

const updateOnlineStatus = () => {
  isOnline.value = navigator.onLine
}

const checkConnection = () => {
  isOnline.value = navigator.onLine
}

onMounted(() => {
  window.addEventListener('online', updateOnlineStatus)
  window.addEventListener('offline', updateOnlineStatus)
})

onUnmounted(() => {
  window.removeEventListener('online', updateOnlineStatus)
  window.removeEventListener('offline', updateOnlineStatus)
})
</script>

<style scoped>
.v-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 24px;
}
</style>

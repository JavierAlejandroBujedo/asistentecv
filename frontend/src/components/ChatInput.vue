<template>
  <div class="chat-footer bg-black w-100 pa-0">
    <div class="max-width-chat mx-auto px-4 pb-2">
      <v-card class="gemini-input-card rounded-xl elevation-0 px-4 py-2 d-flex align-center w-100 mb-2">
        <v-textarea
          v-model="input"
          rows="1"
          auto-grow
          max-rows="10"
          placeholder="Pregunta a ChatCV..."
          variant="plain"
          hide-details
          class="custom-textarea flex-grow-1"
          @keyup.enter.prevent="handleSend"
          :disabled="loading"
        ></v-textarea>
        
        <v-btn
          icon="mdi-send"
          :color="input.trim() ? '#4285f4' : '#ffffff'"
          variant="text"
          size="default"
          class="ml-1 flex-shrink-0"
          :disabled="!input.trim() || loading"
          @click="handleSend"
        ></v-btn>
      </v-card>

      <div class="text-center text-caption text-grey-darken-3 py-2 bg-black">
        Basado en Gemini 1.5 Flash • Contexto de Javier Bujedo
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue';
import { useChat } from '../composables/useChat';

const { sendMessage, loading } = useChat();
const input = ref('');

const handleSend = async () => {
    if (!input.value.trim() || loading.value) return;
    const text = input.value;
    input.value = '';
    await sendMessage(text);
};
</script>

<style scoped>
.max-width-chat {
  max-width: 1100px;
  width: 95%;
}

.gemini-input-card {
  background-color: #1e1f20 !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
}

.custom-textarea :deep(textarea) {
  padding: 12px 0 !important;
  line-height: 1.5 !important;
  color: #ffffff !important;
  font-size: 1.2rem;
}

.custom-textarea :deep(.v-field__overlay),
.custom-textarea :deep(.v-field__outline) {
  display: none !important;
}
</style>

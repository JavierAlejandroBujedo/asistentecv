<template>
  <div class="chat-wrapper bg-black fill-height d-flex flex-column overflow-hidden">
    
    <!-- Greeting (Empty State) -->
    <v-row v-if="history.length === 0 && !isAdmin" align="center" justify="center" class="flex-grow-1 ma-0">
      <v-col cols="12" class="text-center max-width-chat mx-auto px-4">
        <div class="d-flex align-center justify-center mb-2">
          <v-icon size="32" class="gemini-star-icon mr-3">mdi-sparkles</v-icon>
          <span class="text-h4 font-weight-medium text-grey-lighten-2">
            Hola, <span :class="{ 'gemini-gradient': !user && !isAdmin }">{{ greetingName }}</span>
          </span>
        </div>
        <div class="main-title font-weight-bold white-text tracking-tighter">
          ¿Quieres <span :class="{ 'gemini-gradient': user || isAdmin }">conocer a Javier</span>?
        </div>
      </v-col>
    </v-row>

<v-row v-else ref="chatContainer" class="flex-grow-1 overflow-y-auto px-0 ma-0 chat-messages-area custom-scrollbar" align="start">
      <v-col cols="12" class="pa-0">
        <v-container class="max-width-chat pa-0 pb-15">
          <ChatMessage 
            v-for="(msg, i) in history" 
            :key="i" 
            :message="msg" 
          />
          
          <!-- Loading State -->
          <div v-if="loading" class="d-flex align-center px-4 mb-10">
            <v-progress-circular indeterminate size="20" color="#19c37d" class="mr-4"></v-progress-circular>
            <span class="text-caption text-grey-darken-1">Analizando información...</span>
          </div>
        </v-container>
      </v-col>
    </v-row>

    <!-- Input Area -->
    <ChatInput />

  </div>
</template>

<script setup>
import { computed, watch, nextTick, ref } from 'vue';
import { useAuth } from '../composables/useAuth';
import { useChat } from '../composables/useChat';
import ChatMessage from './ChatMessage.vue';
import ChatInput from './ChatInput.vue';

const { user, isAdmin } = useAuth();
const { history, loading } = useChat();
const chatContainer = ref(null);

const greetingName = computed(() => {
  if (isAdmin.value) return "Javier Alejandro";
  return user.value ? user.value.displayName : "Reclutador/a";
});

const scrollToBottom = async () => {
    await nextTick();
    if (chatContainer.value) {
        // chatContainer.value is the v-row, but we need the native element
        const el = chatContainer.value.$el || chatContainer.value;
        el.scrollTop = el.scrollHeight;
    }
};

watch(history, scrollToBottom, { deep: true });
watch(loading, (newVal) => {
    if (newVal) scrollToBottom();
});
</script>



<style scoped>
.chat-wrapper {
  width: 100%;
  height: 100vh;
  position: relative;
  overflow: hidden;
  padding-top: 14vh;
}

.max-width-chat {
  max-width: 1100px;
  width: 95%;
  margin: 0 auto;
}

.chat-messages-area {
  flex: 1;
  max-height: calc(100vh - 14vh - 160px);
}

.gemini-star-icon {
  background: linear-gradient(135deg, #4285f4, #9b72cb, #d96570);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  filter: drop-shadow(0 0 2px rgba(155, 114, 203, 0.3));
}

.gemini-gradient {
  background: linear-gradient(70deg, #4285f4, #9b72cb, #d96570);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  font-weight: 700;
}

.main-title {
  font-size: clamp(2rem, 8vw, 4rem);
  line-height: 1.1;
}

.custom-scrollbar::-webkit-scrollbar {
  display: none;
}
</style>

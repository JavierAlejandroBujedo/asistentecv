<template>
  <div class="mb-12 animate-fade-in px-4">
    <!-- User Message -->
    <div v-if="message.text" class="d-flex align-start mb-8">
      <v-avatar color="#3e3f4b" size="36" class="mr-4 rounded-lg shadow-sm">
        <v-img :src="user?.photoURL" v-if="user?.photoURL"></v-img>
        <v-icon v-else size="20" color="grey-lighten-1">mdi-account</v-icon>
      </v-avatar>
      <div class="message-content text-body-1 pt-1 font-weight-medium text-grey-lighten-4">
        {{ message.text }}
      </div>
    </div>
    
    <!-- AI Message -->
    <div v-if="message.response" class="d-flex align-start bubble-ai">
      <v-avatar color="#19c37d" size="36" class="mr-4 rounded-lg shadow-sm">
        <v-icon color="white" size="24">mdi-robot-outline</v-icon>
      </v-avatar>
      <div 
        class="message-content markdown-body text-body-1 text-grey-lighten-2 pt-1 line-height-xl flex-grow-1"
        v-html="renderMarkdown(message.response)"
      ></div>
    </div>
  </div>
</template>

<script setup>
import { useAuth } from '../composables/useAuth';
import MarkdownIt from 'markdown-it';

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
});

const renderMarkdown = (text) => {
  if (!text) return '';
  return md.render(text);
};

defineProps({
  message: {
    type: Object,
    required: true
  }
});

const { user } = useAuth();
</script>

<style scoped>
.line-height-xl { line-height: 1.75; }

.animate-fade-in {
  animation: fadeIn 0.4s ease-out backwards;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

.message-content {
    max-width: 850px;
}

/* Markdown Styling */
:deep(.markdown-body) {
  word-wrap: break-word;
}

:deep(.markdown-body strong) {
  font-weight: 700;
  color: #fff;
}

:deep(.markdown-body p) {
  margin-bottom: 12px;
}

:deep(.markdown-body p:last-child) {
  margin-bottom: 0;
}

:deep(.markdown-body ul), :deep(.markdown-body ol) {
  padding-left: 20px;
  margin-bottom: 16px;
}

:deep(.markdown-body li) {
  margin-bottom: 4px;
}

:deep(.markdown-body code) {
  background-color: rgba(255, 255, 255, 0.1);
  padding: 2px 5px;
  border-radius: 4px;
  font-family: monospace;
}

.bubble-ai {
    position: relative;
}
</style>

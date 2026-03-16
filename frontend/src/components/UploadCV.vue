<template>
  <v-container fluid class="pa-0 bg-black fill-height overflow-hidden">
    <v-card theme="dark" variant="flat" class="w-100 bg-transparent mx-auto d-flex flex-column" style="height: 100vh; padding: 14vh 4% 2vh 8%;">
      
      <!-- Título y Estado -->
      <div class="d-flex align-center justify-space-between mb-6">
        <div class="text-subtitle-2 font-weight-bold d-flex align-center text-grey-lighten-1" style="letter-spacing: 1px;">
          <v-icon color="#4285f4" class="mr-2" size="20">mdi-file-edit-outline</v-icon>
          GESTIÓN DE CURRICULUM VITAE (CEREBRO RAG)
        </div>
        
        <v-btn
          color="#4285f4"
          variant="flat"
          prepend-icon="mdi-upload"
          class="rounded-pill px-6"
          @click="$refs.fileInput.click()"
          :loading="uploading"
        >
          Subir Nuevo PDF
        </v-btn>
        <input type="file" ref="fileInput" class="d-none" accept=".pdf" @change="e => uploadFile(e.target.files[0])" />
      </div>

      <!-- Grilla de Documentos Activos -->
      <v-card class="bg-transparent border-grey-lite rounded-xl overflow-hidden mb-6 flex-grow-1 d-flex flex-column">
        <v-data-table
          :headers="headers"
          :items="cvFiles"
          :loading="loading"
          class="cv-table compact-table elevation-0"
          no-data-text="No hay ningún CV activo en el sistema. Sube uno para comenzar."
        >
          <!-- Tamaño del archivo -->
          <template v-slot:item.size="{ item }">
            <span class="text-caption text-grey">{{ (item.size / 1024 / 1024).toFixed(2) }} MB</span>
          </template>

          <!-- Fecha de actualización -->
          <template v-slot:item.updated_at="{ item }">
            <span class="text-caption">{{ new Date(item.updated_at * 1000).toLocaleString('es-AR') }}</span>
          </template>

          <!-- Estado -->
          <template v-slot:item.status>
            <v-chip size="x-small" color="success" class="font-weight-bold">ACTIVO EN PINECONE</v-chip>
          </template>

          <!-- Acciones -->
          <template v-slot:item.actions="{ item }">
            <v-btn
              icon="mdi-trash-can-outline"
              variant="text"
              color="error"
              size="small"
              @click="deleteCV(item.name)"
            ></v-btn>
          </template>
        </v-data-table>
      </v-card>

      <!-- Zona de Arrastre (Opcional debajo) -->
      <div 
        class="drop-zone-mini py-4 px-6 text-center"
        :class="{ 'active': isDragging }"
        @dragover.prevent="isDragging = true"
        @dragleave.prevent="isDragging = false"
        @drop.prevent="handleDrop"
      >
        <div class="text-caption text-grey-darken-1 font-weight-bold">
          <v-icon size="small" class="mr-1">mdi-tray-arrow-up</v-icon>
          SUELTA UN PDF AQUÍ PARA REEMPLAZAR EL CV ACTUAL
        </div>
      </div>

      <!-- Alertas -->
      <v-snackbar v-model="alert.show" :color="alert.color" timeout="3000" rounded="pill">
        {{ alert.text }}
      </v-snackbar>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import axios from 'axios';
import { auth } from '../firebase';
import { APP_CONFIG } from '../config';

const cvFiles = ref([]);
const loading = ref(true);
const uploading = ref(false);
const isDragging = ref(false);
const fileInput = ref(null);
const alert = ref({ show: false, text: '', color: '' });

const headers = [
  { title: 'NOMBRE DEL ARCHIVO', key: 'name', align: 'start', sortable: true },
  { title: 'TAMAÑO', key: 'size', sortable: true, width: '120px' },
  { title: 'ÚLTIMA ACTUALIZACIÓN', key: 'updated_at', sortable: true, width: '200px' },
  { title: 'ESTADO', key: 'status', sortable: false, width: '150px' },
  { title: '', key: 'actions', sortable: false, align: 'end', width: '80px' },
];

const fetchCVList = async () => {
  loading.value = true;
  try {
    const token = await auth.currentUser.getIdToken();
    const res = await axios.get(`${APP_CONFIG.API_BASE_URL}/cv-list`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    cvFiles.value = res.data;
  } catch (err) {
    showAlert('Error al cargar la lista de archivos', 'error');
  } finally {
    loading.value = false;
  }
};

const uploadFile = async (file) => {
  if (!file || file.type !== 'application/pdf') {
    showAlert('Por favor, selecciona un archivo PDF válido', 'error');
    return;
  }

  uploading.value = true;
  const formData = new FormData();
  formData.append('file', file);

  try {
    const token = await auth.currentUser.getIdToken();
    await axios.post(`${APP_CONFIG.API_BASE_URL}/upload-cv`, formData, {
      headers: { 
        Authorization: `Bearer ${token}`,
        'Content-Type': 'multipart/form-data'
      }
    });
    showAlert('CV sincronizado con Pinecone con éxito', 'success');
    fetchCVList();
  } catch (err) {
    showAlert('Error en la subida al cerebro RAG', 'error');
  } finally {
    uploading.value = false;
  }
};

const deleteCV = async (filename) => {
  if (!confirm(`¿Estás seguro de que quieres eliminar el CV "${filename}" de Pinecone y del servidor?`)) return;

  try {
    const token = await auth.currentUser.getIdToken();
    await axios.delete(`${APP_CONFIG.API_BASE_URL}/delete-cv/${filename}`, {
      headers: { Authorization: `Bearer ${token}` }
    });
    showAlert('CV eliminado del cerebro RAG', 'success');
    fetchCVList();
  } catch (err) {
    showAlert('No se pudo eliminar el archivo', 'error');
  }
};

const handleDrop = (e) => {
  isDragging.value = false;
  const file = e.dataTransfer.files[0];
  if (file) uploadFile(file);
};

const showAlert = (text, color) => {
  alert.value = { show: true, text, color };
};

onMounted(() => {
  fetchCVList();
});
</script>

<style scoped>
.cv-table {
  background: #0a0a0a !important;
}

.cv-table :deep(thead th) {
  background: #121212 !important;
  color: #4285f4 !important;
  font-weight: 700 !important;
  font-size: 0.65rem !important;
  height: 48px !important;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.cv-table :deep(tbody td) {
  border-bottom: 1px solid rgba(255, 255, 255, 0.02) !important;
  height: 56px !important;
  font-size: 0.85rem !important;
}

.cv-table :deep(tbody tr:hover) {
  background: rgba(66, 133, 244, 0.05) !important;
}

.drop-zone-mini {
  border: 1px dashed rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  transition: all 0.3s ease;
}

.drop-zone-mini.active {
  border-color: #4285f4;
  background: rgba(66, 133, 244, 0.1);
  transform: scale(1.01);
}

.border-grey-lite {
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
}
</style>

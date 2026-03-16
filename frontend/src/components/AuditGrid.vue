<template>
  <v-container fluid class="pa-0 bg-black fill-height overflow-hidden">
    <v-card theme="dark" variant="flat" class="w-100 bg-transparent mx-auto d-flex flex-column" style="height: 100vh; padding: 14vh 4% 2vh 8%;">
      <div class="d-flex align-center justify-space-between mb-4">
        <div class="d-flex align-center">
          <div class="text-subtitle-2 font-weight-bold d-flex align-center text-grey-lighten-1 mr-4" style="letter-spacing: 1px;">
            <v-icon color="#4285f4" class="mr-2" size="20">mdi-account-search-outline</v-icon>
            AUDITORÍA DE CONSULTAS
          </div>
          
          <!-- Botón Borrar Masivo -->
          <v-btn
            v-if="selected.length > 0"
            color="error"
            variant="tonal"
            size="x-small"
            prepend-icon="mdi-trash-can-outline"
            class="rounded-pill px-4"
            @click="deleteSelected"
            :loading="deleting"
          >
            Eliminar {{ selected.length }}
          </v-btn>
        </div>

        <!-- Buscador -->
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          label="Buscar..."
          variant="solo"
          density="compact"
          bg-color="#121212"
          class="audit-search rounded-pill"
          hide-details
          style="max-width: 300px;"
          clearable
        ></v-text-field>
      </div>
      
      <v-data-table
        v-model="selected"
        :headers="headers"
        :items="messages"
        :search="search"
        :loading="loading"
        show-select
        class="audit-table compact-table rounded-lg elevation-0 flex-grow-1"
        hover
        :items-per-page="15"
        no-data-text="Sin registros"
        loading-text="Cargando..."
        fixed-header
      >
        <!-- Formateo de Fecha -->
        <template v-slot:item.timestamp="{ item }">
          <div class="d-flex flex-column" style="min-width: 80px;">
            <span class="text-caption font-weight-bold" style="font-size: 0.7rem !important;">{{ formatDate(item.timestamp).date }}</span>
            <span class="text-caption text-grey" style="font-size: 0.65rem !important;">{{ formatDate(item.timestamp).time }}</span>
          </div>
        </template>

        <!-- Tooltips para Pregunta y Respuesta -->
        <template v-slot:item.prompt="{ item }">
          <div class="text-truncate text-body-2" style="max-width: 180px;">
            {{ item.prompt }}
            <v-tooltip activator="parent" location="top" max-width="400" bgColor="#1e1f20">
              {{ item.prompt }}
            </v-tooltip>
          </div>
        </template>

        <template v-slot:item.response="{ item }">
          <div class="text-truncate text-caption text-grey-lighten-1" style="max-width: 200px;">
            {{ item.response }}
            <v-tooltip activator="parent" location="top" max-width="400" bgColor="#1e1f20">
              {{ item.response }}
            </v-tooltip>
          </div>
        </template>

        <!-- Chip para el Usuario -->
        <template v-slot:item.userName="{ item }">
          <v-chip size="x-small" variant="tonal" color="#4285f4" class="font-weight-bold">
            {{ item.userName || 'Anónimo' }}
          </v-chip>
        </template>

        <!-- Acciones Individuales -->
        <template v-slot:item.actions="{ item }">
          <v-btn
            icon="mdi-delete-outline"
            variant="text"
            color="grey-darken-1"
            size="x-small"
            @click="deleteItem(item.id)"
          ></v-btn>
        </template>
      </v-data-table>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import { db, collection, query, orderBy, onSnapshot, doc, deleteDoc } from '../firebase';

const messages = ref([]);
const selected = ref([]);
const search = ref('');
const loading = ref(true);
const deleting = ref(false);

const headers = [
  { title: 'FECHA', key: 'timestamp', align: 'start', sortable: true, width: '100px' },
  { title: 'USUARIO', key: 'userName', sortable: true, width: '120px' },
  { title: 'CORREO', key: 'userEmail', sortable: true, width: '180px' },
  { title: 'PREGUNTA', key: 'prompt', sortable: false },
  { title: 'RESPUESTA', key: 'response', sortable: false },
  { title: '', key: 'actions', sortable: false, align: 'end', width: '50px' },
];

const formatDate = (ts) => {
  if (!ts) return { date: '-', time: '-' };
  const date = ts.toDate ? ts.toDate() : new Date(ts);
  return {
    date: date.toLocaleDateString('es-AR'),
    time: date.toLocaleTimeString('es-AR', { hour: '2-digit', minute: '2-digit' })
  };
};

const deleteItem = async (id) => {
  if (confirm('¿Eliminar este registro de auditoría?')) {
    try {
      await deleteDoc(doc(db, "chat_history", id));
    } catch (err) {
      console.error("Error al eliminar:", err);
    }
  }
};

const deleteSelected = async () => {
  if (confirm(`¿Eliminar los ${selected.value.length} registros seleccionados?`)) {
    deleting.value = true;
    try {
      const promises = selected.value.map(id => deleteDoc(doc(db, "chat_history", id)));
      await Promise.all(promises);
      selected.value = [];
    } catch (err) {
      console.error("Error en eliminación masiva:", err);
    } finally {
      deleting.value = false;
    }
  }
};

onMounted(() => {
  const q = query(collection(db, "chat_history"), orderBy("timestamp", "desc"));
  onSnapshot(q, (snapshot) => {
    messages.value = snapshot.docs.map(doc => ({ id: doc.id, ...doc.data() }));
    loading.value = false;
  }, (err) => {
    console.error("Error en Auditoría:", err);
    loading.value = false;
  });
});
</script>

<style>
.audit-table.compact-table {
  background: #0a0a0a !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
}

.audit-table.compact-table thead th {
  background: #121212 !important;
  color: #4285f4 !important;
  font-weight: 700 !important;
  font-size: 0.65rem !important;
  height: 40px !important;
  text-transform: uppercase;
  letter-spacing: 1px;
}

/* Zebra Striping - Filas alternas en gris */
.audit-table.compact-table tbody tr:nth-of-type(even) {
  background-color: rgba(255, 255, 255, 0.03) !important;
}

.audit-table.compact-table tbody td {
  border-bottom: 1px solid rgba(255, 255, 255, 0.01) !important;
  height: 48px !important;
  font-size: 0.75rem !important;
  padding: 0 8px !important;
}

.audit-table.compact-table tbody tr:hover {
  background: rgba(66, 133, 244, 0.08) !important;
}

.v-data-table-footer {
  background: #0a0a0a !important;
  font-size: 0.7rem !important;
  min-height: 40px !important;
}

/* Estilo para los checkbox de selección */
.v-selection-control {
  justify-content: center !important;
}
</style>

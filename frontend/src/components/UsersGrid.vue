<template>
  <v-container fluid class="pa-0 bg-black fill-height overflow-hidden">
    <v-card theme="dark" variant="flat" class="w-100 bg-transparent mx-auto d-flex flex-column" style="height: 100vh; padding: 14vh 4% 2vh 8%;">
      <div class="d-flex align-center justify-space-between mb-4">
        <div class="d-flex align-center">
          <div class="text-subtitle-2 font-weight-bold d-flex align-center text-grey-lighten-1 mr-4" style="letter-spacing: 1px;">
            <v-icon color="#34a853" class="mr-2" size="20">mdi-account-group-outline</v-icon>
            GESTIÓN DE USUARIOS
          </div>
        </div>

        <!-- Buscador -->
        <v-text-field
          v-model="search"
          prepend-inner-icon="mdi-magnify"
          label="Buscar usuario..."
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
        :headers="headers"
        :items="users"
        :search="search"
        :loading="loading"
        class="audit-table compact-table rounded-lg elevation-0 flex-grow-1"
        hover
        :items-per-page="15"
        no-data-text="Sin usuarios registrados"
        loading-text="Cargando usuarios..."
        fixed-header
      >
        <template v-slot:item.photoURL="{ item }">
          <v-avatar size="32" class="border-grey-lite">
            <v-img :src="item.photoURL"></v-img>
          </v-avatar>
        </template>
        
        <template v-slot:item.displayName="{ item }">
          <span class="font-weight-bold text-body-2">{{ item.displayName || 'Anónimo' }}</span>
        </template>
        
        <template v-slot:item.email="{ item }">
          <span class="text-grey-lighten-1">{{ item.email }}</span>
        </template>

        <template v-slot:item.role="{ item }">
          <v-switch
            :model-value="item.role === 'admin'"
            @update:model-value="toggleRole(item, $event)"
            color="success"
            density="compact"
            hide-details
            class="my-0 py-0 d-flex justify-center flex-column"
            :loading="updatingUid === item.id"
            :disabled="updatingUid !== null"
          >
            <template v-slot:label>
              <v-chip
                size="x-small"
                variant="outlined"
                :color="item.role === 'admin' ? 'success' : 'grey'"
                class="font-weight-bold px-2 ml-1"
              >
                {{ item.role === 'admin' ? 'ADMIN' : 'USER' }}
              </v-chip>
            </template>
          </v-switch>
        </template>
      </v-data-table>
    </v-card>
  </v-container>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue';
import { auth, db, collection, query, onSnapshot } from '../firebase';
import { APP_CONFIG } from '../config';

// UID del Administrador Maestro — protegido en el frontend
const SUPER_ADMIN_UID = 'y8TIx2FrnKXUYeU64eqCqLAB16e2';

const users = ref([]);
const search = ref('');
const loading = ref(true);
const updatingUid = ref(null); // UID del usuario que se está actualizando

const headers = [
  { title: 'AVATAR', key: 'photoURL', sortable: false, width: '80px', align: 'center' },
  { title: 'NOMBRE', key: 'displayName', sortable: true },
  { title: 'CORREO', key: 'email', sortable: true },
  { title: 'PRIVILEGIOS', key: 'role', sortable: false, width: '150px' }
];

const toggleRole = async (userConfig, isNowAdmin) => {
  // 🔒 Protección Super Admin — bloqueo en el frontend antes de llamar al backend
  if (userConfig.id === SUPER_ADMIN_UID) {
    alert('Acceso denegado: El rol del Administrador Maestro no puede ser modificado.');
    return;
  }

  const newRole = isNowAdmin ? 'admin' : 'user';
  updatingUid.value = userConfig.id;

  console.log(`%c[UsersGrid] 🔄 Cambiando rol de UID: ${userConfig.id} → ${newRole}`, 'color: #a78bfa;');

  try {
    const token = await auth.currentUser?.getIdToken(true);
    if (!token) throw new Error('No hay sesión activa');

    const res = await fetch(`${APP_CONFIG.API_BASE_URL}/admin/update-role`, {
      method: 'PATCH',
      headers: {
        'Content-Type': 'application/json',
        Authorization: `Bearer ${token}`
      },
      body: JSON.stringify({
        target_uid: userConfig.id,
        new_role: newRole
      })
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      console.error(`%c[UsersGrid] ❌ HTTP ${res.status}:`, 'color: #ef4444;', errData);
      throw new Error(errData.detail || `Error HTTP ${res.status}`);
    }

    const responseData = await res.json();
    console.log('%c[UsersGrid] ✅ Rol actualizado:', 'color: #34a853;', responseData);
    updatingUid.value = null;
  } catch (err) {
    updatingUid.value = null;
    console.error('[UsersGrid] ❌ Error al cambiar privilegios:', err.message);
    alert(`No se pudo cambiar el rol:\n${err.message}`);
  }
};

let unsubscribeUsers = null;

onMounted(() => {
  // ⚠️ Solo suscribirse si hay una sesión activa — evita permission-denied en carga inicial
  if (!auth.currentUser) {
    console.debug('[UsersGrid] Sin sesión activa, omitiendo listener de Firestore.');
    loading.value = false;
    return;
  }

  const q = query(collection(db, "users"));
  unsubscribeUsers = onSnapshot(q, (snapshot) => {
    users.value = snapshot.docs.map(doc => {
      const data = doc.data();
      return {
        id: doc.id,
        role: data.role || 'user',
        ...data
      };
    });
    loading.value = false;
    console.log(`%c[UsersGrid] ✅ ${users.value.length} usuarios cargados.`, 'color: #34a853;');
  }, (err) => {
    if (err.code === 'permission-denied' && !auth.currentUser) return;
    console.error('[UsersGrid] ❌ Error cargando usuarios:', err.code, err.message);
    loading.value = false;
  });
});

onUnmounted(() => {
  if (unsubscribeUsers) {
    unsubscribeUsers();
    console.log('%c[UsersGrid] 🔇 Listener de usuarios cancelado.', 'color: #9ca3af;');
  }
});
</script>

<style>
/* Reutilizamos los mismos estilos compactos de la grilla de auditoría */
.audit-table.compact-table {
  background: #0a0a0a !important;
  border: 1px solid rgba(255, 255, 255, 0.05) !important;
}

.audit-table.compact-table thead th {
  background: #121212 !important;
  color: #34a853 !important; /* Verde para usuarios distintos a las consultas */
  font-weight: 700 !important;
  font-size: 0.65rem !important;
  height: 40px !important;
  text-transform: uppercase;
  letter-spacing: 1px;
}

.audit-table.compact-table tbody tr:nth-of-type(even) {
  background-color: rgba(255, 255, 255, 0.03) !important;
}

.audit-table.compact-table tbody td {
  border-bottom: 1px solid rgba(255, 255, 255, 0.01) !important;
  height: 52px !important;
  font-size: 0.85rem !important;
  padding: 0 12px !important;
}

.audit-table.compact-table tbody tr:hover {
  background: rgba(52, 168, 83, 0.08) !important;
}

.v-data-table-footer {
  background: #0a0a0a !important;
  font-size: 0.7rem !important;
  min-height: 40px !important;
}
</style>

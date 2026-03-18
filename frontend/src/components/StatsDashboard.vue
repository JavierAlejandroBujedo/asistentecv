<template>
  <v-container fluid class="pa-0 bg-black fill-height overflow-auto">
    <div class="stats-wrapper">

      <!-- ===== HEADER ===== -->
      <div class="stats-header d-flex align-center justify-space-between mb-6">
        <div class="d-flex align-center gap-3">
          <div class="header-icon-wrap">
            <v-icon size="22" color="#a78bfa">mdi-chart-timeline-variant-shimmer</v-icon>
          </div>
          <div>
            <div class="text-subtitle-2 font-weight-bold text-grey-lighten-1" style="letter-spacing:1px;">
              ESTADÍSTICAS DE CONSUMO
            </div>
            <div class="text-caption text-grey-darken-1">Gemini 1.5 Flash · Capa gratuita</div>
          </div>
        </div>
        <div class="d-flex gap-2">

          <v-btn
            variant="tonal"
            color="#a78bfa"
            size="small"
            prepend-icon="mdi-refresh"
            class="rounded-pill text-none"
            :loading="refreshing"
            @click="loadStats(true)"
          >
            Actualizar
          </v-btn>
        </div>
      </div>

      <v-alert
        v-if="isOffline"
        type="warning"
        variant="tonal"
        class="mb-6 rounded-xl"
        border="start"
      >
        <template v-slot:prepend>
          <v-icon>mdi-wifi-off</v-icon>
        </template>
        <div class="font-weight-bold mb-1">Sin conexión</div>
        <div class="text-body-2">
          ¿Quieres ver números? Aquí tienes uno: <strong>0</strong>. Esa es la cantidad de datos que puedo cargar sin internet. ¡Vuelve cuando recuperes la señal!
        </div>
      </v-alert>

      <!-- ===== SKELETON LOADER (Cold Start) ===== -->
      <template v-if="loading && !isOffline">
        <v-row>
          <v-col v-for="n in 4" :key="n" cols="12" sm="6" lg="3">
            <v-skeleton-loader type="card" class="rounded-xl stat-skeleton" />
          </v-col>
        </v-row>
        <v-row class="mt-2">
          <v-col cols="12" md="8">
            <v-skeleton-loader type="card-avatar, article" class="rounded-xl stat-skeleton" height="300" />
          </v-col>
          <v-col cols="12" md="4">
            <v-skeleton-loader type="card-avatar, article" class="rounded-xl stat-skeleton" height="300" />
          </v-col>
        </v-row>
      </template>

      <!-- ===== ERROR STATE ===== -->
      <v-alert v-else-if="error && !loading" type="error" variant="tonal" class="rounded-xl mb-6">
        {{ error }}
      </v-alert>

      <!-- ===== MAIN CONTENT ===== -->
      <template v-else-if="stats && !loading">

        <!-- KPI Cards -->
        <v-row class="mb-2">
          <v-col cols="12" sm="6" lg="3">
            <div class="kpi-card">
              <div class="kpi-icon" style="background: rgba(167,139,250,0.15);">
                <v-icon size="20" color="#a78bfa">mdi-lightning-bolt</v-icon>
              </div>
              <div class="kpi-value neon-purple">{{ stats.requests_today }}</div>
              <div class="kpi-label">Consultas hoy</div>
              <div class="kpi-sub">Límite: {{ stats.daily_limit }} RPD</div>
            </div>
          </v-col>

          <v-col cols="12" sm="6" lg="3">
            <div class="kpi-card">
              <div class="kpi-icon" style="background: rgba(96,165,250,0.15);">
                <v-icon size="20" color="#60a5fa">mdi-counter</v-icon>
              </div>
              <div class="kpi-value neon-blue">{{ stats.tokens_today.toLocaleString() }}</div>
              <div class="kpi-label">Tokens hoy</div>
              <div class="kpi-sub">Est. aprox. por fragmentación</div>
            </div>
          </v-col>

          <v-col cols="12" sm="6" lg="3">
            <div class="kpi-card">
              <div class="kpi-icon" style="background: rgba(52,211,153,0.15);">
                <v-icon size="20" color="#34d399">mdi-chart-bar</v-icon>
              </div>
              <div class="kpi-value neon-green">{{ stats.average_tokens_per_query }}</div>
              <div class="kpi-label">Tokens promedio / query</div>
              <div class="kpi-sub">Total: {{ stats.total_tokens_used.toLocaleString() }}</div>
            </div>
          </v-col>

          <v-col cols="12" sm="6" lg="3">
            <div class="kpi-card">
              <div class="kpi-icon" style="background: rgba(251,191,36,0.15);">
                <v-icon size="20" color="#fbbf24">mdi-database-outline</v-icon>
              </div>
              <div class="kpi-value neon-yellow">{{ stats.cache_size }}</div>
              <div class="kpi-label">Respuestas en caché</div>
              <div class="kpi-sub">Evitan llamadas a la API</div>
            </div>
          </v-col>
        </v-row>

        <!-- Chart + Gauge Row -->
        <v-row class="mt-2">

          <!-- Area Chart: 7 días -->
          <v-col cols="12" md="8">
            <div class="chart-card">
              <div class="chart-title d-flex align-center gap-2 mb-4">
                <v-icon size="16" color="#a78bfa">mdi-chart-area-spline</v-icon>
                <span>Historial de Consultas (últimos 7 días)</span>
              </div>
              <ApexChart
                type="area"
                height="240"
                :options="areaOptions"
                :series="areaSeries"
              />
            </div>
          </v-col>

          <!-- Gauge: Cuota Diaria -->
          <v-col cols="12" md="4">
            <div class="chart-card d-flex flex-column align-center justify-center">
              <div class="chart-title d-flex align-center gap-2 mb-2" style="align-self: flex-start;">
                <v-icon size="16" color="#60a5fa">mdi-speedometer</v-icon>
                <span>Cuota Diaria Usada</span>
              </div>
              <ApexChart
                type="radialBar"
                height="220"
                :options="gaugeOptions"
                :series="gaugeSeries"
              />
              <div class="text-center mt-2">
                <span class="neon-blue font-weight-bold">{{ stats.requests_today }}</span>
                <span class="text-grey-darken-1 text-caption"> / {{ stats.daily_limit }} RPD</span>
              </div>
              <div class="remaining-badge mt-2">
                <v-icon size="14" color="#34d399" class="mr-1">mdi-shield-check-outline</v-icon>
                <span class="text-caption neon-green">{{ stats.remaining_quota }} disponibles</span>
              </div>
            </div>
          </v-col>
        </v-row>

        <!-- Bar Chart: Tokens por día -->
        <v-row class="mt-2 mb-4">
          <v-col cols="12">
            <div class="chart-card">
              <div class="chart-title d-flex align-center gap-2 mb-4">
                <v-icon size="16" color="#60a5fa">mdi-chart-bar</v-icon>
                <span>Tokens Consumidos por Día</span>
              </div>
              <ApexChart
                type="bar"
                height="200"
                :options="barOptions"
                :series="barSeries"
              />
            </div>
          </v-col>
        </v-row>

      </template>
    </div>
  </v-container>
</template>

<script setup>
import { ref, computed, onMounted, onActivated } from 'vue';
// ✅ CORRECTO: Importar como componente con nombre PascalCase
// Vue Composition API con <script setup> registra automáticamente los imports como componentes
import ApexChart from 'vue3-apexcharts';
import { APP_CONFIG } from '../config';
import { auth } from '../firebase';



const stats = ref(null);
const loading = ref(true);
const refreshing = ref(false);
const error = ref(null);
const isOffline = ref(!navigator.onLine);

window.addEventListener('online', () => { isOffline.value = false; });
window.addEventListener('offline', () => { isOffline.value = true; });

const loadStats = async (isRefresh = false) => {
  if (isOffline.value) return;
  if (isRefresh) refreshing.value = true;
  else loading.value = true;
  error.value = null;

  try {
    // Forzar token fresco (no cacheado) para evitar 401
    const token = await auth.currentUser?.getIdToken(true);
    if (!token) throw new Error('No hay sesión activa. Inicia sesión primero.');

    const res = await fetch(`${APP_CONFIG.API_BASE_URL}/admin/stats`, {
      headers: {
        Authorization: `Bearer ${token}`,
        'Cache-Control': 'no-cache'
      }
    });
    if (!res.ok) {
      const errBody = await res.json().catch(() => ({}));
      throw new Error(errBody.detail || `Error ${res.status}: ${res.statusText}`);
    }
    stats.value = await res.json();
    console.log('[STATS] Datos recibidos:', stats.value);
  } catch (err) {
    error.value = `No se pudieron cargar las estadísticas: ${err.message}`;
    console.error('[STATS ERROR]', err);
  } finally {
    loading.value = false;
    refreshing.value = false;
  }
};



// ─── CHART DATA ───────────────────────────────────────────────
const areaSeries = computed(() => [{
  name: 'Consultas',
  data: stats.value?.history_7d?.map(d => d.requests) ?? []
}]);

const barSeries = computed(() => [{
  name: 'Tokens',
  data: stats.value?.history_7d?.map(d => d.tokens) ?? []
}]);

const gaugeSeries = computed(() => [stats.value?.quota_percentage ?? 0]);

const dayLabels = computed(() =>
  stats.value?.history_7d?.map(d => {
    const [, m, day] = d.date.split('-');
    return `${day}/${m}`;
  }) ?? []
);

// ─── CHART OPTIONS ────────────────────────────────────────────
const sharedTheme = {
  background: 'transparent',
  foreColor: '#6b7280',
};

const areaOptions = computed(() => ({
  chart: { type: 'area', toolbar: { show: false }, zoom: { enabled: false }, ...sharedTheme },
  colors: ['#a78bfa'],
  fill: {
    type: 'gradient',
    gradient: { shadeIntensity: 1, opacityFrom: 0.4, opacityTo: 0.0, stops: [0, 100] }
  },
  stroke: { curve: 'smooth', width: 2.5, colors: ['#a78bfa'] },
  xaxis: {
    categories: dayLabels.value,
    labels: { style: { colors: '#6b7280', fontSize: '11px' } },
    axisBorder: { color: 'rgba(255,255,255,0.05)' },
    axisTicks: { show: false },
  },
  yaxis: { labels: { style: { colors: '#6b7280', fontSize: '11px' } } },
  grid: { borderColor: 'rgba(255,255,255,0.04)', strokeDashArray: 4 },
  tooltip: { theme: 'dark' },
  markers: { size: 4, colors: ['#a78bfa'], strokeColors: '#1a1a2e', strokeWidth: 2 },
  dataLabels: { enabled: false },
}));

const barOptions = computed(() => ({
  chart: { type: 'bar', toolbar: { show: false }, ...sharedTheme },
  colors: ['#60a5fa'],
  fill: {
    type: 'gradient',
    gradient: { shade: 'dark', type: 'vertical', shadeIntensity: 0.4, opacityFrom: 0.9, opacityTo: 0.6, stops: [0, 100] }
  },
  plotOptions: { bar: { borderRadius: 6, columnWidth: '60%' } },
  xaxis: {
    categories: dayLabels.value,
    labels: { style: { colors: '#6b7280', fontSize: '11px' } },
    axisBorder: { color: 'rgba(255,255,255,0.05)' },
    axisTicks: { show: false },
  },
  yaxis: { labels: { style: { colors: '#6b7280', fontSize: '11px' } } },
  grid: { borderColor: 'rgba(255,255,255,0.04)', strokeDashArray: 4 },
  tooltip: { theme: 'dark' },
  dataLabels: { enabled: false },
}));

const gaugeOptions = computed(() => ({
  chart: { type: 'radialBar', ...sharedTheme },
  plotOptions: {
    radialBar: {
      startAngle: -120,
      endAngle: 120,
      hollow: { size: '65%' },
      track: { background: 'rgba(255,255,255,0.05)', strokeWidth: '100%' },
      dataLabels: {
        name: { show: false },
        value: {
          fontSize: '28px',
          fontWeight: 700,
          color: '#60a5fa',
          formatter: (val) => `${val.toFixed(1)}%`
        }
      }
    }
  },
  fill: {
    type: 'gradient',
    gradient: {
      shade: 'dark',
      type: 'horizontal',
      shadeIntensity: 0.5,
      gradientToColors: ['#a78bfa'],
      stops: [0, 100]
    }
  },
  stroke: { lineCap: 'round' },
  colors: ['#60a5fa'],
}));

// Primera carga al montar el componente
onMounted(() => loadStats());

// Recarga CADA VEZ que se navega a la pestaña Estadísticas
// (v-window usa keep-alive internamente → onActivated se dispara al cambiar de tab)
onActivated(() => loadStats(true));

</script>

<style scoped>
.stats-wrapper {
  padding: 14vh 4% 4vh 8%;
  min-height: 100vh;
}

/* Header icon */
.header-icon-wrap {
  width: 40px;
  height: 40px;
  background: rgba(167, 139, 250, 0.1);
  border: 1px solid rgba(167, 139, 250, 0.2);
  border-radius: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
}

/* KPI Cards */
.kpi-card {
  background: #0d0d0f;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 20px 20px 16px;
  transition: border-color 0.25s, transform 0.25s;
  height: 100%;
}
.kpi-card:hover {
  border-color: rgba(167, 139, 250, 0.2);
  transform: translateY(-2px);
}

.kpi-icon {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
}

.kpi-value {
  font-size: 2rem;
  font-weight: 800;
  line-height: 1;
  margin-bottom: 4px;
  letter-spacing: -0.03em;
}

.kpi-label {
  font-size: 0.75rem;
  color: #9ca3af;
  font-weight: 500;
  text-transform: uppercase;
  letter-spacing: 0.07em;
}

.kpi-sub {
  font-size: 0.7rem;
  color: #4b5563;
  margin-top: 4px;
}

/* Chart Cards */
.chart-card {
  background: #0d0d0f;
  border: 1px solid rgba(255, 255, 255, 0.06);
  border-radius: 16px;
  padding: 20px;
  height: 100%;
  transition: border-color 0.25s;
}
.chart-card:hover {
  border-color: rgba(96, 165, 250, 0.15);
}

.chart-title {
  font-size: 0.75rem;
  color: #9ca3af;
  text-transform: uppercase;
  letter-spacing: 0.08em;
  font-weight: 600;
}

/* Neon colors */
.neon-purple { color: #a78bfa; }
.neon-blue   { color: #60a5fa; }
.neon-green  { color: #34d399; }
.neon-yellow { color: #fbbf24; }

.remaining-badge {
  display: flex;
  align-items: center;
  background: rgba(52, 211, 153, 0.08);
  border: 1px solid rgba(52, 211, 153, 0.2);
  border-radius: 20px;
  padding: 4px 10px;
}

/* Skeleton dark override */
:deep(.stat-skeleton .v-skeleton-loader__bone) {
  background: rgba(255,255,255,0.04) !important;
}
</style>

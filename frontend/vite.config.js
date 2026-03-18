import { defineConfig, createLogger } from 'vite'
import vue from '@vitejs/plugin-vue'

const logger = createLogger()
const originalWarn = logger.warn.bind(logger)
logger.warn = (msg, opts) => {
  if (msg.includes('Port')) {
    console.error(`\n🔴 [VITE DEVOPS] Puerto ocupado detectado. Ejecuta: npm run clean-dev\n`)
  }
  originalWarn(msg, opts)
}

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  customLogger: logger,
  server: {
    port: 5173,
    strictPort: false,
    headers: {
      "Cross-Origin-Opener-Policy": "same-origin-allow-popups"
    }
  }
})

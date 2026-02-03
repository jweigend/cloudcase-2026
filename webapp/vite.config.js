import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      // Proxy für Solr um CORS zu umgehen
      '/solr': {
        target: 'http://node1.cloud.local:8983',
        changeOrigin: true,
        rewrite: (path) => path
      },
      // Proxy für Flask Backend auf node0
      '/api': {
        target: 'http://node0.cloud.local:5001',
        changeOrigin: true
      }
    }
  }
})

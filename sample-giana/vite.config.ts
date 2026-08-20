import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { randomUUID } from 'node:crypto'
import { tmpdir } from 'node:os'
import { join } from 'node:path'

export default defineConfig(({ command }) => {
  // Electron/Chromium can retain Windows file handles for source maps after a
  // development run. A unique cache for every Vite server prevents the next
  // launch from trying to unlink files still owned by the previous process.
  const cacheDir = command === 'serve'
    ? join(tmpdir(), 'giana-lex-vite', randomUUID())
    : 'node_modules/.vite-build'

  return {
    base: './',
    cacheDir,
    plugins: [react()],
    // Electron/Chromium may retain handles to old hashed assets on Windows.
    // Never make a valid release build depend on deleting an unreferenced file.
    build: {
      emptyOutDir: false,
    },
    test: {
      environment: 'jsdom',
      setupFiles: './src/test/setup.ts',
      css: true,
      globals: true,
      server: {
        deps: {
          inline: [/@fluentui/, /tabster/],
        },
      },
    },
    server: {
      host: '127.0.0.1',
      proxy: {
        '/api': {
          target: 'http://127.0.0.1:5000',
          changeOrigin: true,
        },
        '/health': {
          target: 'http://127.0.0.1:5000',
          changeOrigin: true,
        },
      },
    },
  }
})

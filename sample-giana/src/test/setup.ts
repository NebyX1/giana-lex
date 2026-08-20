import '@testing-library/jest-dom/vitest'
import { afterEach, beforeEach, vi } from 'vitest'
import { cleanup } from '@testing-library/react'

// Keyborg feature-detects a writable native focus method. Make that contract
// explicit in jsdom, whose descriptor differs from Chromium's.
const nativeFocus = window.HTMLElement.prototype.focus
function resetFocusDescriptor() {
  Object.defineProperty(window.HTMLElement.prototype, 'focus', {
    configurable: true,
    writable: true,
    value: nativeFocus,
  })
}
resetFocusDescriptor()
beforeEach(resetFocusDescriptor)

class TestResizeObserver implements ResizeObserver {
  disconnect() {}
  observe() {}
  unobserve() {}
}
window.ResizeObserver = TestResizeObserver
Object.defineProperty(URL, 'createObjectURL', { configurable: true, writable: true, value: () => 'blob:test' })
Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, writable: true, value: () => undefined })

afterEach(() => {
  cleanup()
  window.localStorage.clear()
  vi.restoreAllMocks()
})

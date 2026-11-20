import '@testing-library/jest-dom/vitest'
import { cleanup } from '@testing-library/react'
import { afterEach, vi } from 'vitest'

import { clearSession } from './native/session'
import { deviceStorage, setNative } from './test-native'

// Tests run in a browser-like environment. The pieces that exist only on a device are
// replaced: the platform check, the secure storage and the login through the system browser.
vi.mock('@capacitor/core', async () => {
  const { isNativeForTests } = await import('./test-native')
  return { Capacitor: { isNativePlatform: isNativeForTests }, CapacitorHttp: {} }
})
vi.mock('@aparajita/capacitor-secure-storage', async () => {
  const { deviceStorage } = await import('./test-native')
  return {
    SecureStorage: {
      get: async (key: string) => deviceStorage.get(key) ?? null,
      set: async (key: string, value: unknown) => void deviceStorage.set(key, structuredClone(value)),
      remove: async (key: string) => void deviceStorage.delete(key),
    },
  }
})
vi.mock('./native/oidc', () => ({ signIn: vi.fn(), refresh: vi.fn() }))

afterEach(async () => {
  cleanup()
  setNative(false)
  await clearSession()
  deviceStorage.clear()
})

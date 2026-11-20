/**
 * What the Android app remembers: which Nexus server it talks to and the tokens it holds.
 * Kept in the device's secure storage, which on Android is encrypted with a key in the Keystore.
 */
import { SecureStorage } from '@aparajita/capacitor-secure-storage'

export interface Tokens {
  accessToken: string
  refreshToken: string | null
  /** When the access token stops working, in milliseconds since the epoch. */
  expiresAt: number
}

export interface Session {
  serverUrl: string
  issuer: string
  clientId: string
  tokens: Tokens | null
}

const KEY = 'session'
let current: Session | null = null

/** Reads the stored session. Call once at start; afterwards `getSession` is enough. */
export async function loadSession(): Promise<Session | null> {
  const stored = await SecureStorage.get(KEY)
  current = stored ? (stored as unknown as Session) : null
  return current
}

export function getSession(): Session | null {
  return current
}

export async function saveSession(session: Session): Promise<void> {
  current = session
  await SecureStorage.set(KEY, session as unknown as Record<string, unknown>)
}

export async function saveTokens(tokens: Tokens | null): Promise<void> {
  if (current) {
    await saveSession({ ...current, tokens })
  }
}

/** Forgets the server and the tokens. */
export async function clearSession(): Promise<void> {
  current = null
  await SecureStorage.remove(KEY)
}

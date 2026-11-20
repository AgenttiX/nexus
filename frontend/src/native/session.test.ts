import { expect, test } from 'vitest'

import { deviceStorage } from '../test-native'
import { clearSession, getSession, loadSession, saveSession, saveTokens, type Session } from './session'

const session: Session = { serverUrl: 'https://nexus.test', issuer: 'https://auth.test/o/', clientId: 'app', tokens: null }
const tokens = { accessToken: 'a', refreshToken: 'r', expiresAt: 1 }

test('there is no session until one is saved', async () => {
  expect(await loadSession()).toBeNull()
  expect(getSession()).toBeNull()
  await saveTokens(tokens)
  expect(deviceStorage.size).toBe(0)
})

test('a saved session survives a restart of the app', async () => {
  await saveSession(session)
  await saveTokens(tokens)
  expect(getSession()).toEqual({ ...session, tokens })
  expect(await loadSession()).toEqual({ ...session, tokens })
  expect(deviceStorage.get('session')).toEqual({ ...session, tokens })
})

test('clearing forgets the server and the tokens', async () => {
  await saveSession({ ...session, tokens })
  await clearSession()
  expect(getSession()).toBeNull()
  expect(await loadSession()).toBeNull()
})

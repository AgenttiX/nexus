import { useMutation } from '@tanstack/react-query'
import { useState, type FormEvent } from 'react'

import { saveSession } from './session'

interface ServerConfig {
  oidc_issuer: string
  oidc_client_id: string
}

/** First screen of the Android app: asks which Nexus server to use, as every deployment has its own. */
export function ServerSetup({ onDone }: { onDone: () => void }) {
  const [address, setAddress] = useState('https://')

  const connect = useMutation({
    mutationFn: async () => {
      const serverUrl = new URL(address).origin
      const response = await globalThis.fetch(new Request(new URL('/api/config/', serverUrl)))
      const config = (await response.json()) as ServerConfig
      if (!response.ok || !config.oidc_client_id) {
        throw new Error('The app is not enabled on this server.')
      }
      await saveSession({ serverUrl, issuer: config.oidc_issuer, clientId: config.oidc_client_id, tokens: null })
    },
    onSuccess: onDone,
  })

  function submit(event: FormEvent) {
    event.preventDefault()
    connect.mutate()
  }

  return (
    <main className="mx-auto max-w-3xl p-6 font-sans">
      <h1 className="text-2xl font-semibold">Nexus</h1>
      <form className="mt-4 grid gap-3" onSubmit={submit}>
        <label className="grid gap-1">
          Address of your Nexus server
          <input
            className="rounded border px-2 py-1"
            type="url"
            required
            pattern="https://.+"
            value={address}
            onChange={(event) => setAddress(event.target.value)}
          />
        </label>
        <button type="submit" className="justify-self-start rounded bg-slate-800 px-4 py-2 text-white">
          Connect
        </button>
        {connect.isError && (
          <p role="alert">
            Could not connect. Check the address, and that this device can reach the server.
          </p>
        )}
      </form>
    </main>
  )
}

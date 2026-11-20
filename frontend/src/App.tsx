import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { useState } from 'react'

import { LOGIN_URL, fetchCurrentUser } from './api/client'
import { ServerSetup } from './native/ServerSetup'
import { signIn } from './native/oidc'
import { isNative } from './native/platform'
import { clearSession, loadSession, saveTokens, type Session } from './native/session'
import { createAppRouter } from './router'

type Router = ReturnType<typeof createAppRouter>

/** In the Android app, signing in happens in the system browser and ends with tokens. */
function NativeSignIn({ session }: { session: Session }) {
  const queryClient = useQueryClient()
  const login = useMutation({
    mutationFn: async () => saveTokens(await signIn(session.issuer, session.clientId)),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['me'] }),
  })
  const forget = useMutation({
    mutationFn: clearSession,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['native-session'] }),
  })
  return (
    <div className="mt-4">
      <button type="button" className="rounded bg-slate-800 px-4 py-2 text-white" onClick={() => login.mutate()}>
        Sign in with a passkey
      </button>
      {login.isError && <p role="alert" className="mt-2">Signing in did not succeed. Try again.</p>}
      <p className="mt-6 text-sm text-slate-600">
        Server: {session.serverUrl}{' '}
        <button type="button" className="underline" onClick={() => forget.mutate()}>
          Use another server
        </button>
      </p>
    </div>
  )
}

/** Shows the application to signed-in users, and the way to sign in to everyone else. */
function Shell({ router: givenRouter, session }: { router?: Router; session?: Session }) {
  const [router] = useState(() => givenRouter ?? createAppRouter())
  const { data: user, isPending, isError } = useQuery({ queryKey: ['me'], queryFn: fetchCurrentUser })

  if (user) {
    return <RouterProvider router={router} />
  }
  return (
    <main className="mx-auto max-w-3xl p-6 font-sans">
      <h1 className="text-2xl font-semibold">Nexus</h1>
      {isPending && <p className="mt-4">Loading…</p>}
      {isError && <p className="mt-4">Nexus could not be reached. Reload the page to try again.</p>}
      {user === null &&
        (session ? (
          <NativeSignIn session={session} />
        ) : (
          <a className="mt-4 inline-block rounded bg-slate-800 px-4 py-2 text-white" href={LOGIN_URL}>
            Sign in with a passkey
          </a>
        ))}
    </main>
  )
}

/** The Android app first needs to know its server; the stored choice is read from secure storage. */
function NativeApp({ router }: { router?: Router }) {
  const queryClient = useQueryClient()
  const session = useQuery({ queryKey: ['native-session'], queryFn: loadSession })
  if (session.isPending) {
    return null
  }
  if (!session.data) {
    return <ServerSetup onDone={() => queryClient.invalidateQueries({ queryKey: ['native-session'] })} />
  }
  return <Shell router={router} session={session.data} />
}

export function App({ router }: { router?: Router }) {
  return isNative() ? <NativeApp router={router} /> : <Shell router={router} />
}

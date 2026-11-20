import { useQuery } from '@tanstack/react-query'

import { LOGIN_URL, fetchCurrentUser } from './api/client'

export function App() {
  const { data: user, isPending, isError } = useQuery({ queryKey: ['me'], queryFn: fetchCurrentUser })

  return (
    <main className="mx-auto max-w-3xl p-6 font-sans">
      <h1 className="text-2xl font-semibold">Nexus</h1>
      {isPending && <p className="mt-4">Loading…</p>}
      {isError && <p className="mt-4">Nexus could not be reached. Reload the page to try again.</p>}
      {user === null && (
        <a className="mt-4 inline-block rounded bg-slate-800 px-4 py-2 text-white" href={LOGIN_URL}>
          Sign in with a passkey
        </a>
      )}
      {user && <p className="mt-4">Signed in as {user.username}.</p>}
    </main>
  )
}

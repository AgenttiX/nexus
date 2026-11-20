import { useQuery } from '@tanstack/react-query'
import { RouterProvider } from '@tanstack/react-router'
import { useState } from 'react'

import { LOGIN_URL, fetchCurrentUser } from './api/client'
import { createAppRouter } from './router'

type Router = ReturnType<typeof createAppRouter>

/** Shows the application to signed-in users, and the way to sign in to everyone else. */
export function App({ router: givenRouter }: { router?: Router }) {
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
      {user === null && (
        <a className="mt-4 inline-block rounded bg-slate-800 px-4 py-2 text-white" href={LOGIN_URL}>
          Sign in with a passkey
        </a>
      )}
    </main>
  )
}

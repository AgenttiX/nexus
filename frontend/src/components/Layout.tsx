import { useQueryClient } from '@tanstack/react-query'
import { Link, Outlet } from '@tanstack/react-router'

import { isNative } from '../native/platform'
import { saveTokens } from '../native/session'

export function Layout() {
  const queryClient = useQueryClient()
  return (
    <div className="mx-auto max-w-5xl p-6 font-sans">
      <nav className="mb-6 flex flex-wrap items-baseline gap-x-6 gap-y-2 border-b border-slate-200 pb-3">
        <Link to="/" className="text-2xl font-semibold">
          Nexus
        </Link>
        <Link to="/news" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          News
        </Link>
        <Link to="/calendar" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Calendar
        </Link>
        <Link to="/time" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Time
        </Link>
        <Link to="/sleep" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Sleep
        </Link>
        <Link to="/finance" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Finances
        </Link>
        <Link to="/investments" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Investments
        </Link>
        <Link to="/food" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Food
        </Link>
        {isNative() ? (
          <button
            type="button"
            className="ml-auto text-slate-600"
            onClick={() => void saveTokens(null).then(() => queryClient.invalidateQueries({ queryKey: ['me'] }))}
          >
            Sign out
          </button>
        ) : (
          <a href="/accounts/logout/" className="ml-auto text-slate-600">
            Sign out
          </a>
        )}
      </nav>
      <Outlet />
    </div>
  )
}

export function HomePage() {
  return <p>Choose a section above.</p>
}

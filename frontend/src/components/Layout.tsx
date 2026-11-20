import { Link, Outlet } from '@tanstack/react-router'

export function Layout() {
  return (
    <div className="mx-auto max-w-5xl p-6 font-sans">
      <nav className="mb-6 flex items-baseline gap-6 border-b border-slate-200 pb-3">
        <Link to="/" className="text-2xl font-semibold">
          Nexus
        </Link>
        <Link to="/news" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          News
        </Link>
        <Link to="/calendar" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Calendar
        </Link>
        <Link to="/sleep" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Sleep
        </Link>
        <Link to="/finance" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Finances
        </Link>
        <Link to="/food" className="text-slate-600 [&.active]:font-semibold [&.active]:text-slate-900">
          Food
        </Link>
      </nav>
      <Outlet />
    </div>
  )
}

export function HomePage() {
  return <p>Choose a section above.</p>
}

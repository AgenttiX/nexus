import { createRootRoute, createRoute, createRouter } from '@tanstack/react-router'

import { HomePage, Layout } from './components/Layout'
import { CalendarPage } from './features/calendars/CalendarPage'
import { FinancePage } from './features/finance/FinancePage'
import { FoodPage } from './features/food/FoodPage'
import { InvestmentsPage } from './features/investments/InvestmentsPage'
import { NewsPage } from './features/news/NewsPage'
import { SleepPage } from './features/sleep/SleepPage'
import { TimePage } from './features/timetracking/TimePage'

const rootRoute = createRootRoute({ component: Layout })
const routeTree = rootRoute.addChildren([
  createRoute({ getParentRoute: () => rootRoute, path: '/', component: HomePage }),
  createRoute({ getParentRoute: () => rootRoute, path: '/news', component: NewsPage }),
  createRoute({ getParentRoute: () => rootRoute, path: '/calendar', component: CalendarPage }),
  createRoute({ getParentRoute: () => rootRoute, path: '/time', component: TimePage }),
  createRoute({ getParentRoute: () => rootRoute, path: '/sleep', component: SleepPage }),
  createRoute({ getParentRoute: () => rootRoute, path: '/finance', component: FinancePage }),
  createRoute({ getParentRoute: () => rootRoute, path: '/investments', component: InvestmentsPage }),
  createRoute({ getParentRoute: () => rootRoute, path: '/food', component: FoodPage }),
])

export function createAppRouter(history?: Parameters<typeof createRouter>[0]['history']) {
  return createRouter({ routeTree, history })
}

declare module '@tanstack/react-router' {
  interface Register {
    router: ReturnType<typeof createAppRouter>
  }
}

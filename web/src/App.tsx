import { Nav } from './components/Nav'
import { Toast } from './components/Toast'
import { ViewHost } from './components/ViewHost'
import { ReportScreen } from './screens/ReportScreen'
import { RunningScreen } from './screens/RunningScreen'
import { TranslateScreen } from './screens/TranslateScreen'
import { useHash, type Route } from './state/router'

function render(route: Route) {
  if (route.name === 'running' && route.id) return <RunningScreen id={route.id} key={route.id} />
  if (route.name === 'report' && route.id) return <ReportScreen id={route.id} key={route.id} />
  return <TranslateScreen />
}

export function App() {
  const hash = useHash()
  return (
    <>
      <div className="wrap">
        <Nav />
        <main>
          <ViewHost hash={hash} render={render} />
        </main>
      </div>
      <Toast />
    </>
  )
}

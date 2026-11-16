import { createRoot } from 'react-dom/client'
import { App } from './App'
import { StoreProvider } from './state/store'
import './styles/tokens.css'
import './styles/base.css'
import './styles/nav.css'
import './styles/buttons.css'
import './styles/panel.css'
import './styles/editor.css'
import './styles/steps.css'
import './styles/report.css'
import './styles/data.css'
import './styles/history.css'
import './styles/export.css'
import './styles/toast.css'

createRoot(document.getElementById('root') as HTMLElement).render(
  <StoreProvider>
    <App />
  </StoreProvider>
)

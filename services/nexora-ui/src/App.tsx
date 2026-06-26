import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { ToastProvider } from './components/Toast'
import Layout from './components/Layout'
import Devices from './pages/Devices'
import Plugins from './pages/Plugins'
import Executions from './pages/Executions'
import Ports from './pages/Ports'
import Webservices from './pages/Webservices'
import Telemetry from './pages/Telemetry'
import SLO from './pages/SLO'
import Fleets from './pages/Fleets'

export default function App() {
  return (
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Navigate to="/devices" replace />} />
            <Route path="devices"     element={<Devices />} />
            <Route path="plugins"     element={<Plugins />} />
            <Route path="executions"  element={<Executions />} />
            <Route path="ports"       element={<Ports />} />
            <Route path="webservices" element={<Webservices />} />
            <Route path="telemetry"   element={<Telemetry />} />
            <Route path="slo"         element={<SLO />} />
            <Route path="fleets"      element={<Fleets />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  )
}

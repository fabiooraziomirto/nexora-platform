import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Layout from './components/Layout'
import Devices from './pages/Devices'
import Telemetry from './pages/Telemetry'
import SLO from './pages/SLO'
import Fleets from './pages/Fleets'

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Navigate to="/devices" replace />} />
          <Route path="devices"   element={<Devices />} />
          <Route path="telemetry" element={<Telemetry />} />
          <Route path="slo"       element={<SLO />} />
          <Route path="fleets"    element={<Fleets />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { useEffect } from 'react'
import { ToastProvider } from './components/Toast'
import { AuthProvider, useAuth } from './auth/AuthContext'
import { setAuthTokenProvider } from './api/client'
import Layout from './components/Layout'
import Dashboard from './pages/Dashboard'
import Devices from './pages/Devices'
import Plugins from './pages/Plugins'
import Executions from './pages/Executions'
import Ports from './pages/Ports'
import Webservices from './pages/Webservices'
import Telemetry from './pages/Telemetry'
import SLO from './pages/SLO'
import Fleets from './pages/Fleets'
import AIInsights from './pages/AIInsights'
import AIRisk from './pages/AIRisk'
import AIFunctionBuilder from './pages/AIFunctionBuilder'
import Login from './pages/Login'
import Audit from './pages/Audit'
import OnboardingWizard from './pages/OnboardingWizard'

function AuthenticatedLayout() {
  const auth = useAuth()
  const keycloakConfigured = Boolean(import.meta.env.VITE_KEYCLOAK_URL)

  useEffect(() => {
    setAuthTokenProvider(auth.getAccessToken)
  }, [auth])

  if (auth.loading) {
    return <div className="min-h-screen bg-slate-50" />
  }
  if (keycloakConfigured && !auth.authenticated) {
    return <Navigate to="/login" replace />
  }
  return <Layout />
}

export default function App() {
  return (
    <AuthProvider>
      <ToastProvider>
        <BrowserRouter>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/" element={<AuthenticatedLayout />}>
              <Route index element={<Navigate to="/dashboard" replace />} />
              <Route path="dashboard" element={<Dashboard />} />
              <Route path="onboarding" element={<OnboardingWizard />} />
              <Route path="devices"     element={<Devices />} />
              <Route path="plugins"     element={<Plugins />} />
              <Route path="executions"  element={<Executions />} />
              <Route path="ports"       element={<Ports />} />
              <Route path="webservices" element={<Webservices />} />
              <Route path="telemetry"   element={<Telemetry />} />
              <Route path="slo"         element={<SLO />} />
              <Route path="fleets"      element={<Fleets />} />
              <Route path="audit"       element={<Audit />} />
              <Route path="ai-insights" element={<AIInsights />} />
              <Route path="ai-risk"     element={<AIRisk />} />
              <Route path="ai-functions" element={<AIFunctionBuilder />} />
            </Route>
          </Routes>
        </BrowserRouter>
      </ToastProvider>
    </AuthProvider>
  )
}

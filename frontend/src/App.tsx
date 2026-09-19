import { HealthStatus } from './components/HealthStatus'

function App() {
  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-start justify-center gap-8 p-6">
      <header>
        <h1 className="text-3xl font-bold tracking-tight text-slate-900">
          Dynamic Data Entry Platform
        </h1>
        <p className="mt-2 text-slate-600">
          Phase&nbsp;0 — frontend is running. The card below verifies
          communication with the FastAPI backend.
        </p>
      </header>

      <HealthStatus />

      <footer className="text-xs text-slate-400">
        React + TypeScript + Vite + Tailwind CSS
      </footer>
    </main>
  )
}

export default App
import { HealthStatus } from "./components/HealthStatus";

export function App() {
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between px-4 py-4">
          <h1 className="text-lg font-semibold tracking-tight">Wind Forecast Monitor</h1>
          <HealthStatus />
        </div>
      </header>
      <main className="mx-auto max-w-5xl px-4 py-10">
        <p className="text-slate-600">
          National wind forecasts and actual generation for the UK day-ahead desk.
        </p>
      </main>
    </div>
  );
}

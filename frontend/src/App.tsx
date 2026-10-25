import { CoverageBadge } from "./components/CoverageBadge";
import { DecisionCutoffProvider } from "./components/DecisionCutoffProvider";
import { DecisionView } from "./components/DecisionView";
import { HealthStatus } from "./components/HealthStatus";

export function App() {
  return (
    <DecisionCutoffProvider>
      <div className="min-h-screen bg-paper text-ink">
        <header className="border-b border-rule bg-surface">
          <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-3 px-4 py-4">
            <h1 className="text-lg font-semibold tracking-tight">Wind Forecast Monitor</h1>
            <div className="flex flex-wrap items-center gap-2">
              <CoverageBadge />
              <HealthStatus />
            </div>
          </div>
        </header>
        <main className="mx-auto max-w-5xl px-4 py-10">
          <DecisionView />
        </main>
      </div>
    </DecisionCutoffProvider>
  );
}

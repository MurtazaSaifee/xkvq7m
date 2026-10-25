import { useState } from "react";

import { AccuracyView } from "./components/AccuracyView";
import { CoverageBadge } from "./components/CoverageBadge";
import { DecisionCutoffProvider } from "./components/DecisionCutoffProvider";
import { DecisionView } from "./components/DecisionView";
import { HealthStatus } from "./components/HealthStatus";
import { MethodologyView } from "./components/MethodologyView";
import { ViewTabs } from "./components/ViewTabs";
import { searchForDay } from "./decision/dayQuery";
import { searchForView, viewFromSearch, type ViewId } from "./views/views";

/** The header, the view tabs and the active view. The active view is kept in the URL. */
function AppShell() {
  const [view, setView] = useState<ViewId>(() => viewFromSearch(window.location.search));

  const selectView = (next: ViewId) => {
    const url = new URL(window.location.href);
    url.search = searchForView(window.location.search, next);
    window.history.replaceState(window.history.state, "", url);
    setView(next);
  };

  // Opens the Decision view for one delivery day. The day goes into the URL with the view, so the
  // Decision view mounts on that day and the link can be shared.
  const openDecision = (day: string) => {
    const url = new URL(window.location.href);
    url.search = searchForView(searchForDay(window.location.search, day), "decision");
    window.history.replaceState(window.history.state, "", url);
    setView("decision");
  };

  return (
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
      <main className="mx-auto max-w-5xl space-y-8 px-4 py-10">
        <ViewTabs active={view} onSelect={selectView} />
        {view === "decision" && <DecisionView />}
        {view === "accuracy" && <AccuracyView onOpenDecision={openDecision} />}
        {view === "methodology" && <MethodologyView />}
      </main>
    </div>
  );
}

export function App() {
  return (
    <DecisionCutoffProvider>
      <AppShell />
    </DecisionCutoffProvider>
  );
}

import { useEffect, useState } from "react";
import RunList from "./components/RunList";
import RunView from "./components/RunView";

// Tiny hash router: "#/" = list, "#/run/<id>" = one run. No library needed for two pages,
// and hash URLs work from a static file server without rewrites.
function useHashRoute(): string | null {
  const read = () => {
    const m = window.location.hash.match(/^#\/run\/(.+)$/);
    return m ? decodeURIComponent(m[1]) : null;
  };
  const [runId, setRunId] = useState(read);
  useEffect(() => {
    const onChange = () => {
      setRunId(read());
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", onChange);
    return () => window.removeEventListener("hashchange", onChange);
  }, []);
  return runId;
}

export default function App() {
  const runId = useHashRoute();
  return (
    <div className="mx-auto max-w-6xl px-4 py-6">
      <header className="mb-6 flex items-baseline justify-between gap-4">
        <a href="#/" className="text-xl font-semibold hover:underline">
          Incident Investigation Agent
        </a>
        <span className="text-sm text-slate-500">trajectory viewer · read-only</span>
      </header>
      {runId ? <RunView id={runId} /> : <RunList />}
    </div>
  );
}

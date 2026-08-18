import { NavLink, Route, Routes } from "react-router-dom";
import Analytics from "./pages/Analytics";
import PipelineStatus from "./pages/PipelineStatus";
import PublishHistory from "./pages/PublishHistory";
import ReviewQueue from "./pages/ReviewQueue";
import Scripts from "./pages/Scripts";
import Settings from "./pages/Settings";
import Trends from "./pages/Trends";
import { NeuCard } from "./components/Neu";

const NAV_ITEMS = [
  { to: "/", label: "Pipeline status" },
  { to: "/trends", label: "Trends" },
  { to: "/scripts", label: "Scripts" },
  { to: "/review", label: "Review queue" },
  { to: "/publish-history", label: "Publish history" },
  { to: "/analytics", label: "Analytics" },
  { to: "/settings", label: "Settings" },
];

export default function App() {
  return (
    <div className="min-h-screen flex gap-6 p-6">
      <nav className="w-56 shrink-0">
        <NeuCard className="space-y-1 sticky top-6">
          <h1 className="text-base font-semibold mb-4 px-1">Faceless Pipeline</h1>
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `block rounded-neu-sm px-3 py-2 text-sm transition-all ${
                  isActive
                    ? "shadow-neu-pressed-sm text-neu-accent"
                    : "text-neu-muted hover:shadow-neu-raised-xs hover:text-neu-text"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </NeuCard>
      </nav>
      <main className="flex-1 min-w-0">
        <Routes>
          <Route path="/" element={<PipelineStatus />} />
          <Route path="/trends" element={<Trends />} />
          <Route path="/scripts" element={<Scripts />} />
          <Route path="/review" element={<ReviewQueue />} />
          <Route path="/publish-history" element={<PublishHistory />} />
          <Route path="/analytics" element={<Analytics />} />
          <Route path="/settings" element={<Settings />} />
        </Routes>
      </main>
    </div>
  );
}

import { NavLink, Route, Routes } from "react-router-dom";
import Analytics from "./pages/Analytics";
import PipelineStatus from "./pages/PipelineStatus";
import PublishHistory from "./pages/PublishHistory";
import ReviewQueue from "./pages/ReviewQueue";
import Scripts from "./pages/Scripts";
import Settings from "./pages/Settings";
import Trends from "./pages/Trends";

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
    <div className="min-h-screen flex">
      <nav className="w-56 shrink-0 border-r border-slate-800 p-4 space-y-1">
        <h1 className="text-lg font-semibold mb-4">Faceless Pipeline</h1>
        {NAV_ITEMS.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.to === "/"}
            className={({ isActive }) =>
              `block rounded px-3 py-2 text-sm ${
                isActive ? "bg-slate-800 text-white" : "text-slate-400 hover:bg-slate-900"
              }`
            }
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="flex-1 p-6">
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

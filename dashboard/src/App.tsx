import { NavLink, Route, Routes } from "react-router-dom";
import {
  Activity,
  CheckCircle2,
  FileText,
  Flame,
  LineChart,
  PawPrint,
  Send,
  Settings as SettingsIcon,
} from "lucide-react";
import Analytics from "./pages/Analytics";
import PipelineStatus from "./pages/PipelineStatus";
import PublishHistory from "./pages/PublishHistory";
import ReviewQueue from "./pages/ReviewQueue";
import Scripts from "./pages/Scripts";
import Settings from "./pages/Settings";
import Trends from "./pages/Trends";
import { NeuCard, NeuIcon } from "./components/Neu";

const NAV_ITEMS = [
  { to: "/", label: "Pipeline status", icon: Activity },
  { to: "/trends", label: "Trends", icon: Flame },
  { to: "/scripts", label: "Scripts", icon: FileText },
  { to: "/review", label: "Review queue", icon: CheckCircle2 },
  { to: "/publish-history", label: "Publish history", icon: Send },
  { to: "/analytics", label: "Analytics", icon: LineChart },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function App() {
  return (
    <div className="min-h-screen flex gap-6 p-6">
      <nav className="w-56 shrink-0">
        <NeuCard className="space-y-1 sticky top-6">
          <h1 className="text-base font-semibold mb-4 px-1 flex items-center gap-2">
            <NeuIcon>
              <PawPrint size={16} className="text-neu-accent" aria-hidden="true" />
            </NeuIcon>
            Faceless Pipeline
          </h1>
          {NAV_ITEMS.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex items-center gap-3 rounded-neu-sm px-2 py-2 text-sm transition-all ${
                    isActive
                      ? "shadow-neu-pressed-sm text-neu-accent"
                      : "text-neu-muted hover:shadow-neu-raised-xs hover:text-neu-text"
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <NeuIcon active={isActive}>
                      <Icon size={16} aria-hidden="true" />
                    </NeuIcon>
                    {item.label}
                  </>
                )}
              </NavLink>
            );
          })}
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

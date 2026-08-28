import { useEffect, useState } from "react";
import { NavLink, Route, Routes } from "react-router-dom";
import {
  Activity,
  CalendarClock,
  CheckCircle2,
  FileText,
  Flame,
  LineChart,
  LogOut,
  PawPrint,
  Send,
  Settings as SettingsIcon,
} from "lucide-react";
import { api } from "./api";
import Analytics from "./pages/Analytics";
import Login from "./pages/Login";
import PipelineStatus from "./pages/PipelineStatus";
import PublishHistory from "./pages/PublishHistory";
import ReviewQueue from "./pages/ReviewQueue";
import Scheduled from "./pages/Scheduled";
import Scripts from "./pages/Scripts";
import Settings from "./pages/Settings";
import Trends from "./pages/Trends";
import { NeuButton, NeuCard, NeuIcon } from "./components/Neu";
import { ToastProvider } from "./components/Toasts";
import { ThemeToggle } from "./components/ThemeToggle";

const NAV_ITEMS = [
  { to: "/", label: "Pipeline status", icon: Activity },
  { to: "/trends", label: "Trends", icon: Flame },
  { to: "/scripts", label: "Scripts", icon: FileText },
  { to: "/review", label: "Review queue", icon: CheckCircle2 },
  { to: "/scheduled", label: "Scheduled", icon: CalendarClock },
  { to: "/publish-history", label: "Publish history", icon: Send },
  { to: "/analytics", label: "Analytics", icon: LineChart },
  { to: "/settings", label: "Settings", icon: SettingsIcon },
];

export default function App() {
  // null = still checking; DASHBOARD_PASSWORD unset means the backend
  // always reports authenticated: true, so this gate is invisible
  // (no login screen, no logout button) unless auth is actually turned on.
  const [auth, setAuth] = useState<{ enabled: boolean; authenticated: boolean } | null>(null);

  useEffect(() => {
    api.authStatus().then(setAuth);
  }, []);

  async function logout() {
    await api.logout();
    setAuth((prev) => (prev ? { ...prev, authenticated: false } : prev));
  }

  if (auth === null) return null;
  if (!auth.authenticated) {
    return <Login onSuccess={() => setAuth({ enabled: true, authenticated: true })} />;
  }

  return (
    <ToastProvider>
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
            <div className="pt-3 space-y-1">
              <ThemeToggle />
              {auth.enabled && (
                <NeuButton className="w-full justify-center text-xs" onClick={logout}>
                  <LogOut size={14} aria-hidden="true" />
                  Log out
                </NeuButton>
              )}
            </div>
          </NeuCard>
        </nav>
        <main className="flex-1 min-w-0">
          <Routes>
            <Route path="/" element={<PipelineStatus />} />
            <Route path="/trends" element={<Trends />} />
            <Route path="/scripts" element={<Scripts />} />
            <Route path="/review" element={<ReviewQueue />} />
            <Route path="/scheduled" element={<Scheduled />} />
            <Route path="/publish-history" element={<PublishHistory />} />
            <Route path="/analytics" element={<Analytics />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </ToastProvider>
  );
}

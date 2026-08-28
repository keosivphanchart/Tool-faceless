import { useEffect, useState } from "react";
import { api } from "../api";
import { NeuBadge, NeuButton, NeuCard, NeuToggle } from "../components/Neu";
import { useToast } from "../components/Toasts";

const PLATFORM_LABEL = { youtube: "YouTube", tiktok: "TikTok", instagram: "Instagram" } as const;
type Platform = keyof typeof PLATFORM_LABEL;
const PLATFORM_ORDER: Platform[] = ["youtube", "tiktok", "instagram"];
const REQUIRED_ENV_VAR: Record<Platform, string> = {
  youtube: "YOUTUBE_CLIENT_SECRETS_FILE",
  tiktok: "TIKTOK_CLIENT_KEY",
  instagram: "INSTAGRAM_APP_ID",
};
const DISCONNECT_FN: Record<Platform, () => Promise<unknown>> = {
  youtube: api.disconnectYouTube,
  tiktok: api.disconnectTikTok,
  instagram: api.disconnectInstagram,
};

function ConnectAccountsCard({
  accounts,
  reload,
}: {
  accounts: Awaited<ReturnType<typeof api.accountsStatus>>;
  reload: () => void;
}) {
  const { notify } = useToast();
  const [disconnecting, setDisconnecting] = useState<string | null>(null);

  async function disconnect(platform: Platform) {
    setDisconnecting(platform);
    try {
      await DISCONNECT_FN[platform]();
      notify("success", `${PLATFORM_LABEL[platform]} disconnected`);
      reload();
    } catch (err) {
      notify("error", `Failed to disconnect ${PLATFORM_LABEL[platform]}`, (err as Error).message);
    } finally {
      setDisconnecting(null);
    }
  }

  return (
    <NeuCard>
      <h3 className="text-sm font-medium text-neu-muted mb-3">Connected accounts</h3>
      <table className="w-full text-sm">
        <tbody className="divide-y divide-neu-shadowDark/60">
          {PLATFORM_ORDER.map((platform) => {
            const account = accounts[platform];
            return (
              <tr key={platform}>
                <td className="py-2">{PLATFORM_LABEL[platform]}</td>
                <td className="py-2">
                  <NeuToggle on={account.connected} label={account.connected ? "connected" : "not connected"} />
                </td>
                <td className="py-2 text-right">
                  {account.connected ? (
                    <NeuButton
                      variant="danger"
                      loading={disconnecting === platform}
                      onClick={() => disconnect(platform)}
                    >
                      Disconnect
                    </NeuButton>
                  ) : account.configured ? (
                    <NeuButton
                      variant="primary"
                      onClick={() => {
                        window.location.href = `/api/publish/accounts/${platform}/connect`;
                      }}
                    >
                      Connect {PLATFORM_LABEL[platform]}
                    </NeuButton>
                  ) : (
                    <span className="text-xs text-neu-muted">Set {REQUIRED_ENV_VAR[platform]} in .env first</span>
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </NeuCard>
  );
}

export default function Settings() {
  const [status, setStatus] = useState<Awaited<ReturnType<typeof api.settingsStatus>> | null>(null);
  const [accounts, setAccounts] = useState<Awaited<ReturnType<typeof api.accountsStatus>> | null>(null);
  const { notify } = useToast();

  const loadAccounts = () => api.accountsStatus().then(setAccounts);

  useEffect(() => {
    api.settingsStatus().then(setStatus);
    loadAccounts();

    // The OAuth connect flow round-trips through the platform's consent
    // screen and lands back here via a full-page redirect (not a fetch),
    // so success/failure arrives as a query param rather than a response.
    const params = new URLSearchParams(window.location.search);
    const connected = params.get("connected");
    const error = params.get("error");
    if (connected) notify("success", `${PLATFORM_LABEL[connected as Platform] ?? connected} connected`);
    if (error) notify("error", "Failed to connect account", error);
    if (connected || error) window.history.replaceState({}, "", window.location.pathname);
  }, []);

  if (!status || !accounts) return <p className="text-neu-muted text-sm">Loading...</p>;

  return (
    <div className="space-y-8">
      <div>
        <h2 className="text-xl font-semibold">Settings</h2>
        <p className="text-sm text-neu-muted mt-1">
          API keys live in <code className="text-neu-text">.env</code> only and are never sent to this
          dashboard — this page shows configuration status, not values. Edit <code>.env</code> and restart the
          backend to change them. YouTube/TikTok/Instagram accounts themselves are connected below.
        </p>
      </div>

      <ConnectAccountsCard accounts={accounts} reload={loadAccounts} />

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">Niche keywords (TREND_SEED_KEYWORDS)</h3>
        <div className="flex flex-wrap gap-2">
          {status.trend_seed_keywords.map((k) => (
            <NeuBadge key={k}>{k}</NeuBadge>
          ))}
        </div>
      </NeuCard>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">Reddit subreddits (REDDIT_SUBREDDITS)</h3>
        <div className="flex flex-wrap gap-2">
          {status.reddit_subreddits.map((k) => (
            <NeuBadge key={k}>r/{k}</NeuBadge>
          ))}
        </div>
      </NeuCard>

      <NeuCard className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <span className="text-neu-muted">Voice profile (KOKORO_VOICE): </span>
          {status.voice_profile}
        </div>
        <div>
          <span className="text-neu-muted">Script provider (SCRIPT_PROVIDER): </span>
          {status.script_provider}
        </div>
        <div>
          <span className="text-neu-muted">
            {status.script_provider.toUpperCase()}_MODEL:{" "}
          </span>
          {status.script_model}
        </div>
      </NeuCard>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">API keys / credentials</h3>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-neu-shadowDark/60">
            {Object.entries(status.credentials_configured).map(([key, configured]) => (
              <tr key={key}>
                <td className="py-2">{key}</td>
                <td className="py-2">
                  <NeuToggle on={configured} label={configured ? "configured" : "missing"} />
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </NeuCard>

      <NeuCard>
        <h3 className="text-sm font-medium text-neu-muted mb-3">
          Automation — all opt-in, set in <code className="text-neu-text">.env</code>
        </h3>
        <table className="w-full text-sm">
          <tbody className="divide-y divide-neu-shadowDark/60">
            {[
              ["AUTO_GENERATE_ENABLED", status.automation.auto_generate_enabled],
              ["AUTO_TREND_FINDER_ENABLED", status.automation.auto_trend_finder_enabled],
              ["AUTO_APPROVE_ENABLED", status.automation.auto_approve_enabled],
              ["AB_TEST_ENABLED", status.automation.ab_test_enabled],
              ["DIGEST_ENABLED", status.automation.digest_enabled],
              ["CLEANUP_ENABLED", status.automation.cleanup_enabled],
            ].map(([key, on]) => (
              <tr key={key as string}>
                <td className="py-2">{key}</td>
                <td className="py-2">
                  <NeuToggle on={on as boolean} label={on ? "on" : "off"} />
                </td>
              </tr>
            ))}
            <tr>
              <td className="py-2">Daily / monthly LLM budget</td>
              <td className="py-2 text-neu-muted">
                {status.automation.daily_cost_budget_usd > 0 ? `$${status.automation.daily_cost_budget_usd}/day` : "unlimited"}
                {" · "}
                {status.automation.monthly_cost_budget_usd > 0
                  ? `$${status.automation.monthly_cost_budget_usd}/mo`
                  : "unlimited"}
              </td>
            </tr>
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}

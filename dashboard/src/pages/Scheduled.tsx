import { useEffect, useState } from "react";
import { api, BestPostingTime, PostingSlot, ReviewVideo } from "../api";
import { NeuBadge, NeuButton, NeuCard, NeuInput, NeuToggle } from "../components/Neu";
import { useToast } from "../components/Toasts";

const DAY_LABELS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
const PLATFORM_LABELS: Record<string, string> = { youtube: "YouTube", tiktok: "TikTok" };

function formatHour(hour: number): string {
  return `${hour.toString().padStart(2, "0")}:00 UTC`;
}

function BestTimesCard({ times }: { times: Record<string, BestPostingTime[]> }) {
  const platforms = Object.keys(times);

  return (
    <NeuCard>
      <h3 className="text-sm font-medium text-neu-muted mb-1">Best times to post</h3>
      <p className="text-xs text-neu-muted mb-3">
        Ranked by average views, from performance already pulled for your published videos.
      </p>
      {platforms.length === 0 ? (
        <p className="text-sm text-neu-muted">Not enough published + analyzed videos yet to suggest a time.</p>
      ) : (
        <div className="space-y-3">
          {platforms.map((platform) => (
            <div key={platform}>
              <p className="text-xs font-semibold text-neu-accent uppercase tracking-wide mb-1.5">
                {PLATFORM_LABELS[platform] ?? platform}
              </p>
              <div className="flex flex-wrap gap-2">
                {times[platform].map((t) => (
                  <NeuBadge key={t.hour}>
                    {formatHour(t.hour)} · avg {Math.round(t.avg_views).toLocaleString()} views ({t.sample_count}{" "}
                    {t.sample_count === 1 ? "post" : "posts"})
                  </NeuBadge>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </NeuCard>
  );
}

function NewSlotForm({ onCreated }: { onCreated: () => void }) {
  const { notify } = useToast();
  const [label, setLabel] = useState("");
  const [time, setTime] = useState("18:00");
  const [days, setDays] = useState<number[]>([]);
  const [platforms, setPlatforms] = useState<string[]>([]);
  const [saving, setSaving] = useState(false);

  function toggleDay(day: number) {
    setDays((prev) => (prev.includes(day) ? prev.filter((d) => d !== day) : [...prev, day].sort()));
  }

  function togglePlatform(platform: string) {
    setPlatforms((prev) => (prev.includes(platform) ? prev.filter((p) => p !== platform) : [...prev, platform]));
  }

  async function submit() {
    if (days.length === 0) {
      notify("error", "Pick at least one day");
      return;
    }
    setSaving(true);
    try {
      await api.createSlot({ label, days_of_week: days, time_of_day: time, platforms: platforms.length ? platforms : null });
      notify("success", "Recurring slot added");
      setLabel("");
      setDays([]);
      setPlatforms([]);
      onCreated();
    } catch (err) {
      notify("error", "Could not add slot", err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-3 pt-4 border-t border-neu-shadowDark/60">
      <div className="flex flex-wrap items-center gap-2">
        <NeuInput placeholder="Label (optional)" value={label} onChange={(e) => setLabel(e.target.value)} className="w-40" />
        <NeuInput type="time" value={time} onChange={(e) => setTime(e.target.value)} className="w-28" />
        <span className="text-xs text-neu-muted">UTC</span>
      </div>
      <div className="flex flex-wrap gap-1.5">
        {DAY_LABELS.map((label, i) => (
          <button
            key={i}
            onClick={() => toggleDay(i)}
            className={`px-2.5 py-1 rounded-neu-sm text-xs shadow-neu-raised-xs transition-all ${
              days.includes(i) ? "text-neu-accent shadow-neu-pressed-sm" : "text-neu-muted"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
      <div className="flex flex-wrap gap-1.5 items-center">
        <span className="text-xs text-neu-muted mr-1">Platforms:</span>
        {Object.entries(PLATFORM_LABELS).map(([key, label]) => (
          <button
            key={key}
            onClick={() => togglePlatform(key)}
            className={`px-2.5 py-1 rounded-neu-sm text-xs shadow-neu-raised-xs transition-all ${
              platforms.includes(key) ? "text-neu-accent shadow-neu-pressed-sm" : "text-neu-muted"
            }`}
          >
            {label}
          </button>
        ))}
        <span className="text-xs text-neu-muted">(none selected = auto-detect, same as immediate publish)</span>
      </div>
      <NeuButton variant="primary" loading={saving} onClick={submit}>
        Add recurring slot
      </NeuButton>
    </div>
  );
}

function RecurringScheduleCard({ slots, reload }: { slots: PostingSlot[]; reload: () => void }) {
  const { notify } = useToast();
  const [busyId, setBusyId] = useState<number | null>(null);

  async function toggleEnabled(slot: PostingSlot) {
    setBusyId(slot.id);
    try {
      await api.updateSlot(slot.id, { enabled: !slot.enabled });
      reload();
    } catch (err) {
      notify("error", "Could not update slot", err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  async function remove(slot: PostingSlot) {
    if (!window.confirm(`Delete recurring slot "${slot.label || slot.time_of_day}"?`)) return;
    setBusyId(slot.id);
    try {
      await api.deleteSlot(slot.id);
      notify("success", "Slot deleted");
      reload();
    } catch (err) {
      notify("error", "Could not delete slot", err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <NeuCard>
      <h3 className="text-sm font-medium text-neu-muted mb-1">Recurring schedule</h3>
      <p className="text-xs text-neu-muted mb-3">
        Fires at its day/time and publishes whichever approved video has been waiting longest — no need to pick a
        datetime by hand for every video. Checked every minute in the background.
      </p>

      <div className="grid grid-cols-7 gap-2 mb-4">
        {DAY_LABELS.map((label, day) => (
          <div key={day} className="rounded-neu-sm shadow-neu-pressed-sm p-2 space-y-1 min-h-[4rem]">
            <p className="text-[10px] uppercase tracking-wide text-neu-muted font-semibold text-center">{label}</p>
            {slots
              .filter((s) => s.days_of_week.includes(day))
              .sort((a, b) => a.time_of_day.localeCompare(b.time_of_day))
              .map((s) => (
                <div
                  key={s.id}
                  className={`text-[10px] text-center rounded px-1 py-0.5 ${s.enabled ? "text-neu-accent" : "text-neu-muted line-through"}`}
                >
                  {s.time_of_day}
                </div>
              ))}
          </div>
        ))}
      </div>

      {slots.length > 0 && (
        <table className="w-full text-sm mb-2">
          <thead className="text-left text-neu-muted">
            <tr>
              <th className="pb-2 font-medium">Label</th>
              <th className="pb-2 font-medium">Days</th>
              <th className="pb-2 font-medium">Time</th>
              <th className="pb-2 font-medium">Platforms</th>
              <th className="pb-2 font-medium">Enabled</th>
              <th></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neu-shadowDark/60">
            {slots.map((s) => (
              <tr key={s.id}>
                <td className="py-2">{s.label || "—"}</td>
                <td className="py-2">{s.days_of_week.map((d) => DAY_LABELS[d]).join(", ")}</td>
                <td className="py-2">{s.time_of_day} UTC</td>
                <td className="py-2">{s.platforms ? s.platforms.map((p) => PLATFORM_LABELS[p] ?? p).join(", ") : "auto"}</td>
                <td className="py-2">
                  <button disabled={busyId === s.id} onClick={() => toggleEnabled(s)}>
                    <NeuToggle on={s.enabled} label={s.enabled ? "on" : "off"} />
                  </button>
                </td>
                <td className="py-2 text-right">
                  <NeuButton variant="danger" loading={busyId === s.id} onClick={() => remove(s)}>
                    Delete
                  </NeuButton>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      <NewSlotForm onCreated={reload} />
    </NeuCard>
  );
}

/** Approved videos waiting on a future publish time, plus the recurring
 * posting schedule that draws from the approved queue automatically. A
 * scheduled video leaves the pending Review queue the moment it's
 * scheduled, and won't show up in Publish history until it actually goes
 * out — without this page there'd be no way to see what's queued and for
 * when, or to change your mind before it fires. */
export default function Scheduled() {
  const [videos, setVideos] = useState<ReviewVideo[]>([]);
  const [slots, setSlots] = useState<PostingSlot[]>([]);
  const [bestTimes, setBestTimes] = useState<Record<string, BestPostingTime[]>>({});
  const [busyId, setBusyId] = useState<number | null>(null);
  const { notify } = useToast();

  const loadVideos = () => api.listScheduled().then(setVideos);
  const loadSlots = () => api.listSlots().then(setSlots);

  useEffect(() => {
    loadVideos();
    loadSlots();
    api.bestPostingTimes().then(setBestTimes);
  }, []);

  async function unschedule(id: number) {
    if (!window.confirm("Cancel this scheduled publish? The video stays approved, just not on a schedule.")) return;

    setBusyId(id);
    try {
      await api.unscheduleVideo(id);
      notify("success", "Schedule cancelled");
      loadVideos();
    } catch (err) {
      notify("error", "Could not cancel", err instanceof Error ? err.message : String(err));
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Scheduler</h2>

      <BestTimesCard times={bestTimes} />
      <RecurringScheduleCard slots={slots} reload={loadSlots} />

      <div>
        <h3 className="text-sm font-medium text-neu-muted mb-1">Individually scheduled ({videos.length} upcoming)</h3>
        <p className="text-xs text-neu-muted mb-3">
          Published automatically at the time shown — checked every minute in the background, no need to keep this
          page open.
        </p>
      </div>

      <NeuCard>
        <table className="w-full text-sm">
          <thead className="text-left text-neu-muted">
            <tr>
              <th className="pb-3 font-medium">Topic</th>
              <th className="pb-3 font-medium">Publishes at</th>
              <th className="pb-3 font-medium"></th>
            </tr>
          </thead>
          <tbody className="divide-y divide-neu-shadowDark/60">
            {videos.map((v) => (
              <tr key={v.id}>
                <td className="py-3">{v.script.topic}</td>
                <td>
                  <NeuBadge>{v.scheduled_for ? new Date(v.scheduled_for).toLocaleString() : "—"}</NeuBadge>
                </td>
                <td className="text-right">
                  <NeuButton
                    variant="danger"
                    loading={busyId === v.id}
                    disabled={busyId !== null && busyId !== v.id}
                    onClick={() => unschedule(v.id)}
                  >
                    {busyId === v.id ? "Cancelling..." : "Cancel"}
                  </NeuButton>
                </td>
              </tr>
            ))}
            {videos.length === 0 && (
              <tr>
                <td colSpan={3} className="py-6 text-center text-neu-muted">
                  Nothing individually scheduled. Schedule a video from the Review queue, or set up a recurring slot
                  above.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </NeuCard>
    </div>
  );
}

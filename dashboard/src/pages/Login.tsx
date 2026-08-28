import { FormEvent, useState } from "react";
import { PawPrint } from "lucide-react";
import { api } from "../api";
import { NeuButton, NeuCard, NeuIcon, NeuInput } from "../components/Neu";

export default function Login({ onSuccess }: { onSuccess: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      await api.login(password);
      onSuccess();
    } catch {
      setError("Wrong password.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <NeuCard className="w-full max-w-sm space-y-5">
        <div className="flex items-center gap-2">
          <NeuIcon>
            <PawPrint size={16} className="text-neu-accent" aria-hidden="true" />
          </NeuIcon>
          <h1 className="text-base font-semibold">Faceless Pipeline</h1>
        </div>

        <form onSubmit={submit} className="space-y-3">
          <NeuInput
            type="password"
            autoFocus
            placeholder="Dashboard password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full"
          />
          {error && <p className="text-xs text-neu-danger">{error}</p>}
          <NeuButton type="submit" variant="primary" loading={loading} className="w-full justify-center">
            Log in
          </NeuButton>
        </form>
      </NeuCard>
    </div>
  );
}

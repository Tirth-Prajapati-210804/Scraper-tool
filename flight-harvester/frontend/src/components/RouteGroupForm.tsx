import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import {
  createRouteGroup,
  createRouteGroupFromText,
  updateRouteGroup,
} from "../api/route-groups";
import { useToast } from "../context/ToastContext";
import type { RouteGroup } from "../types/route-group";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";

interface RouteGroupFormProps {
  open: boolean;
  onClose: () => void;
  initial?: RouteGroup | null;
}

// ── Quick-setup form (plain text: "Canada" → "Vietnam") ──────────────────────

interface QuickState {
  origin: string;
  destination: string;
  nights: number;
  days_ahead: number;
}

function QuickForm({
  onSuccess,
  onClose,
}: {
  onSuccess: () => void;
  onClose: () => void;
}) {
  const { showToast } = useToast();
  const [form, setForm] = useState<QuickState>({
    origin: "",
    destination: "",
    nights: 10,
    days_ahead: 365,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [resolved, setResolved] = useState<{
    origins: string[];
    destinations: string[];
    name: string;
  } | null>(null);

  function set<K extends keyof QuickState>(key: K, value: QuickState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
    setResolved(null);
    setError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const res = await createRouteGroupFromText({
        origin: form.origin.trim(),
        destination: form.destination.trim(),
        nights: form.nights,
        days_ahead: form.days_ahead,
      });
      setResolved({
        origins: res.resolved_origins,
        destinations: res.resolved_destinations,
        name: res.group.name,
      });
      showToast(`Created: ${res.group.name}`, "success");
      onSuccess();
    } catch (err: unknown) {
      const msg =
        (err as { response?: { data?: { detail?: string } } })?.response?.data
          ?.detail ?? "Could not resolve location. Try a different name.";
      setError(msg);
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-5">
      {/* Route input */}
      <div className="flex items-center gap-3">
        <div className="flex-1">
          <label className="field-label">From</label>
          <input
            className="field-input"
            value={form.origin}
            onChange={(e) => set("origin", e.target.value)}
            required
            placeholder="Canada"
            autoFocus
          />
        </div>
        <div className="mt-5 text-xl font-bold text-slate-400">→</div>
        <div className="flex-1">
          <label className="field-label">To</label>
          <input
            className="field-input"
            value={form.destination}
            onChange={(e) => set("destination", e.target.value)}
            required
            placeholder="Vietnam"
          />
        </div>
      </div>

      <p className="text-xs text-slate-500">
        Type a country or city name. Examples: <em>Canada</em>, <em>Japan</em>,{" "}
        <em>Tokyo</em>, <em>Bali</em>, <em>London</em>.
        You can also combine: <em>Tokyo, Osaka</em> or use IATA codes directly:{" "}
        <em>YYZ, YVR</em>.
      </p>

      {/* Options */}
      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="field-label">Nights at destination</label>
          <input
            type="number"
            min={1}
            max={90}
            className="field-input"
            value={form.nights}
            onChange={(e) => set("nights", Number(e.target.value))}
            required
          />
        </div>
        <div>
          <label className="field-label">Days ahead to track</label>
          <input
            type="number"
            min={1}
            max={730}
            className="field-input"
            value={form.days_ahead}
            onChange={(e) => set("days_ahead", Number(e.target.value))}
            required
          />
        </div>
      </div>

      {/* Resolution preview (shown after successful create) */}
      {resolved && (
        <div className="rounded-lg border border-green-200 bg-green-50 p-3 text-sm">
          <p className="font-medium text-green-800">{resolved.name}</p>
          <p className="mt-1 text-green-700">
            <span className="font-medium">Origins:</span>{" "}
            {resolved.origins.join(", ")}
          </p>
          <p className="text-green-700">
            <span className="font-medium">Destinations:</span>{" "}
            {resolved.destinations.join(", ")}
          </p>
        </div>
      )}

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 pt-1">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={saving}>
          {resolved ? "Add another" : "Create route"}
        </Button>
      </div>
    </form>
  );
}

// ── Advanced form (raw IATA codes, same as before) ────────────────────────────

interface AdvancedState {
  name: string;
  destination_label: string;
  destinations: string;
  origins: string;
  nights: number;
  days_ahead: number;
  is_active: boolean;
}

function toAdvancedState(rg?: RouteGroup | null): AdvancedState {
  if (!rg) {
    return {
      name: "",
      destination_label: "",
      destinations: "",
      origins: "",
      nights: 12,
      days_ahead: 365,
      is_active: true,
    };
  }
  return {
    name: rg.name,
    destination_label: rg.destination_label,
    destinations: rg.destinations.join(", "),
    origins: rg.origins.join(", "),
    nights: rg.nights,
    days_ahead: rg.days_ahead,
    is_active: rg.is_active,
  };
}

function AdvancedForm({
  initial,
  onSuccess,
  onClose,
}: {
  initial?: RouteGroup | null;
  onSuccess: () => void;
  onClose: () => void;
}) {
  const { showToast } = useToast();
  const [form, setForm] = useState<AdvancedState>(() =>
    toAdvancedState(initial),
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(toAdvancedState(initial));
    setError(null);
  }, [initial]);

  function set<K extends keyof AdvancedState>(key: K, value: AdvancedState[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        destination_label: form.destination_label.trim(),
        destinations: form.destinations
          .split(",")
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean),
        origins: form.origins
          .split(",")
          .map((s) => s.trim().toUpperCase())
          .filter(Boolean),
        nights: form.nights,
        days_ahead: form.days_ahead,
        is_active: form.is_active,
      };
      if (initial) {
        await updateRouteGroup(initial.id, payload);
      } else {
        await createRouteGroup(payload);
      }
      showToast("Route group saved", "success");
      onSuccess();
    } catch {
      setError("Failed to save. Please check your input and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label className="field-label">Name</label>
        <input
          className="field-input"
          value={form.name}
          onChange={(e) => set("name", e.target.value)}
          required
          placeholder="CAD-Tokyo-Shanghai-CAD"
        />
      </div>

      <div>
        <label className="field-label">Destination Label</label>
        <input
          className="field-input"
          value={form.destination_label}
          onChange={(e) => set("destination_label", e.target.value)}
          required
          placeholder="TYO/SHA"
        />
      </div>

      <div>
        <label className="field-label">Origin airports (comma-separated IATA)</label>
        <input
          className="field-input"
          value={form.origins}
          onChange={(e) => set("origins", e.target.value)}
          required
          placeholder="YYZ, YVR, YEG"
        />
      </div>

      <div>
        <label className="field-label">Destination airports (comma-separated IATA)</label>
        <input
          className="field-input"
          value={form.destinations}
          onChange={(e) => set("destinations", e.target.value)}
          required
          placeholder="TYO, SHA"
        />
      </div>

      <div className="grid grid-cols-2 gap-4">
        <div>
          <label className="field-label">Nights</label>
          <input
            type="number"
            min={1}
            className="field-input"
            value={form.nights}
            onChange={(e) => set("nights", Number(e.target.value))}
            required
          />
        </div>
        <div>
          <label className="field-label">Days Ahead</label>
          <input
            type="number"
            min={1}
            className="field-input"
            value={form.days_ahead}
            onChange={(e) => set("days_ahead", Number(e.target.value))}
            required
          />
        </div>
      </div>

      <label className="flex cursor-pointer items-center gap-2 text-sm text-slate-700">
        <input
          type="checkbox"
          checked={form.is_active}
          onChange={(e) => set("is_active", e.target.checked)}
          className="rounded border-slate-300 text-brand-600 focus:ring-brand-500"
        />
        Active
      </label>

      {error && (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">
          {error}
        </p>
      )}

      <div className="flex justify-end gap-2 pt-2">
        <Button type="button" variant="secondary" onClick={onClose}>
          Cancel
        </Button>
        <Button type="submit" variant="primary" loading={saving}>
          {initial ? "Save changes" : "Create"}
        </Button>
      </div>
    </form>
  );
}

// ── Main export ───────────────────────────────────────────────────────────────

export function RouteGroupForm({ open, onClose, initial }: RouteGroupFormProps) {
  const qc = useQueryClient();
  // When editing an existing group, go straight to advanced mode
  const [tab, setTab] = useState<"quick" | "advanced">(
    initial ? "advanced" : "quick",
  );

  useEffect(() => {
    setTab(initial ? "advanced" : "quick");
  }, [initial, open]);

  async function handleSuccess() {
    await qc.invalidateQueries({ queryKey: ["route-groups"] });
    if (initial) {
      await qc.invalidateQueries({ queryKey: ["route-group", initial.id] });
      onClose();
    }
    // For new groups in Quick mode, stay open so user sees the confirmation
    // and can optionally add another. They close manually.
  }

  const title = initial ? "Edit Route Group" : "New Route Group";

  return (
    <Modal open={open} onClose={onClose} title={title}>
      {/* Tab bar — only shown when creating a new group */}
      {!initial && (
        <div className="mb-5 flex rounded-lg border border-slate-200 bg-slate-50 p-1">
          <button
            type="button"
            onClick={() => setTab("quick")}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === "quick"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Quick Setup
          </button>
          <button
            type="button"
            onClick={() => setTab("advanced")}
            className={`flex-1 rounded-md px-3 py-1.5 text-sm font-medium transition-colors ${
              tab === "advanced"
                ? "bg-white text-slate-900 shadow-sm"
                : "text-slate-500 hover:text-slate-700"
            }`}
          >
            Manual (IATA codes)
          </button>
        </div>
      )}

      {tab === "quick" && !initial ? (
        <QuickForm onSuccess={handleSuccess} onClose={onClose} />
      ) : (
        <AdvancedForm
          initial={initial}
          onSuccess={handleSuccess}
          onClose={onClose}
        />
      )}
    </Modal>
  );
}

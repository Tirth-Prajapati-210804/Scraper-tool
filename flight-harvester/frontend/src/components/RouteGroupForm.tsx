import { useQueryClient } from "@tanstack/react-query";
import { type FormEvent, useEffect, useState } from "react";
import { createRouteGroup, updateRouteGroup } from "../api/route-groups";
import type { RouteGroup } from "../types/route-group";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";

interface RouteGroupFormProps {
  open: boolean;
  onClose: () => void;
  initial?: RouteGroup | null;
}

interface FormState {
  name: string;
  destination_label: string;
  destinations: string;
  origins: string;
  nights: number;
  days_ahead: number;
  is_active: boolean;
}

function toFormState(rg?: RouteGroup | null): FormState {
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

export function RouteGroupForm({ open, onClose, initial }: RouteGroupFormProps) {
  const qc = useQueryClient();
  const [form, setForm] = useState<FormState>(() => toFormState(initial));
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(toFormState(initial));
    setError(null);
  }, [initial, open]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
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
      await qc.invalidateQueries({ queryKey: ["route-groups"] });
      if (initial) {
        await qc.invalidateQueries({ queryKey: ["route-group", initial.id] });
      }
      onClose();
    } catch {
      setError("Failed to save. Please check your input and try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title={initial ? "Edit Route Group" : "New Route Group"}
    >
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
          <label className="field-label">Destinations (comma-separated)</label>
          <input
            className="field-input"
            value={form.destinations}
            onChange={(e) => set("destinations", e.target.value)}
            required
            placeholder="TYO, SHA"
          />
        </div>

        <div>
          <label className="field-label">Origins (comma-separated)</label>
          <input
            className="field-input"
            value={form.origins}
            onChange={(e) => set("origins", e.target.value)}
            required
            placeholder="YYZ, YVR, YEG"
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
    </Modal>
  );
}

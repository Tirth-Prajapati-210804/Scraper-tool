/**
 * SearchProfileForm — create a new search profile with one or more legs.
 *
 * A leg is a single flight segment: From → To.
 * For multi-city journeys you chain legs:
 *   Leg 1: AMD → BOM  (wait 6+ hours)
 *   Leg 2: BOM → DEL  (wait 24+ hours)
 *   Leg 3: DEL → JFK  (final)
 *
 * The "From" and "To" fields accept plain text:
 *   "India", "Ahmedabad", "AMD", "TYO, SHA", "Canada, USA" — anything the
 *   backend location resolver understands.
 */
import { useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { createSearchProfile } from "../api/search-profiles";
import { useToast } from "../context/ToastContext";
import type { SearchLegCreate } from "../types/search-profile";
import { Button } from "./ui/Button";
import { Modal } from "./ui/Modal";

interface Props {
  open: boolean;
  onClose: () => void;
}

interface LegDraft extends SearchLegCreate {
  // UI-only id for React key
  _key: number;
}

let _nextKey = 0;
function newLeg(isFirst = false): LegDraft {
  return {
    _key: _nextKey++,
    origin_query: "",
    destination_query: "",
    min_halt_hours: isFirst ? null : 6,
    max_halt_hours: null,
  };
}

export function SearchProfileForm({ open, onClose }: Props) {
  const qc = useQueryClient();
  const { showToast } = useToast();

  const [name, setName] = useState("");
  const [daysAhead, setDaysAhead] = useState(365);
  const [legs, setLegs] = useState<LegDraft[]>(() => [newLeg(true)]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  function reset() {
    setName("");
    setDaysAhead(365);
    setLegs([newLeg(true)]);
    setError(null);
  }

  function updateLeg<K extends keyof SearchLegCreate>(
    key: number,
    field: K,
    value: SearchLegCreate[K],
  ) {
    setLegs((ls) => ls.map((l) => (l._key === key ? { ...l, [field]: value } : l)));
  }

  function addLeg() {
    setLegs((ls) => [...ls, newLeg(false)]);
  }

  function removeLeg(key: number) {
    setLegs((ls) => ls.filter((l) => l._key !== key));
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      await createSearchProfile({
        name: name.trim(),
        days_ahead: daysAhead,
        is_active: true,
        legs: legs.map(({ _key: _k, ...rest }) => ({
          ...rest,
          // Last leg must have null min_halt_hours
          min_halt_hours: rest === legs[legs.length - 1] ? null : rest.min_halt_hours,
        })),
      });
      await qc.invalidateQueries({ queryKey: ["search-profiles"] });
      showToast("Search profile created", "success");
      reset();
      onClose();
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail ?? "Failed to create profile. Check your location names.");
    } finally {
      setSaving(false);
    }
  }

  const isMultiLeg = legs.length > 1;

  return (
    <Modal open={open} onClose={onClose} title="New Search Profile">
      <form onSubmit={handleSubmit} className="space-y-5">
        {/* Profile name + days ahead */}
        <div className="grid grid-cols-3 gap-3">
          <div className="col-span-2">
            <label className="field-label">Profile name</label>
            <input
              className="field-input"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              placeholder="India to USA"
              autoFocus
            />
          </div>
          <div>
            <label className="field-label">Days ahead</label>
            <input
              type="number"
              min={1}
              max={730}
              className="field-input"
              value={daysAhead}
              onChange={(e) => setDaysAhead(Number(e.target.value))}
              required
            />
          </div>
        </div>

        {/* Legs */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <span className="text-sm font-medium text-slate-700">
              {isMultiLeg ? "Flight legs" : "Route"}
            </span>
            <button
              type="button"
              onClick={addLeg}
              className="flex items-center gap-1 text-xs font-medium text-brand-600 hover:text-brand-700"
            >
              <Plus className="h-3.5 w-3.5" />
              Add leg
            </button>
          </div>

          {legs.map((leg, idx) => {
            const isFinal = idx === legs.length - 1;
            return (
              <div
                key={leg._key}
                className="rounded-lg border border-slate-200 bg-slate-50 p-3 space-y-3"
              >
                {/* Leg header */}
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase tracking-wide">
                    {isMultiLeg ? `Leg ${idx + 1}` : "Route"}
                    {isFinal && isMultiLeg ? " · Final" : ""}
                  </span>
                  {legs.length > 1 && (
                    <button
                      type="button"
                      onClick={() => removeLeg(leg._key)}
                      className="text-slate-400 hover:text-red-500"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </button>
                  )}
                </div>

                {/* From → To */}
                <div className="flex items-center gap-2">
                  <div className="flex-1">
                    <label className="field-label">From</label>
                    <input
                      className="field-input"
                      value={leg.origin_query}
                      onChange={(e) => updateLeg(leg._key, "origin_query", e.target.value)}
                      required
                      placeholder='e.g. "India" or "AMD"'
                    />
                  </div>
                  <div className="mt-5 text-slate-400 font-bold">→</div>
                  <div className="flex-1">
                    <label className="field-label">To</label>
                    <input
                      className="field-input"
                      value={leg.destination_query}
                      onChange={(e) =>
                        updateLeg(leg._key, "destination_query", e.target.value)
                      }
                      required
                      placeholder='e.g. "USA" or "JFK, LAX"'
                    />
                  </div>
                </div>

                {/* Halt requirement — shown for all legs except the final one */}
                {!isFinal && (
                  <div className="flex items-center gap-3">
                    <div className="flex-1">
                      <label className="field-label">
                        Min wait at this destination before next flight
                      </label>
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          min={0}
                          step={0.5}
                          className="field-input"
                          value={leg.min_halt_hours ?? ""}
                          onChange={(e) =>
                            updateLeg(
                              leg._key,
                              "min_halt_hours",
                              e.target.value === "" ? null : Number(e.target.value),
                            )
                          }
                          placeholder="6"
                        />
                        <span className="text-sm text-slate-500 whitespace-nowrap">hours</span>
                      </div>
                    </div>
                    <div className="flex-1">
                      <label className="field-label">Max wait (optional)</label>
                      <div className="flex items-center gap-1">
                        <input
                          type="number"
                          min={0}
                          step={0.5}
                          className="field-input"
                          value={leg.max_halt_hours ?? ""}
                          onChange={(e) =>
                            updateLeg(
                              leg._key,
                              "max_halt_hours",
                              e.target.value === "" ? null : Number(e.target.value),
                            )
                          }
                          placeholder="No limit"
                        />
                        <span className="text-sm text-slate-500 whitespace-nowrap">hours</span>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>

        {/* Hint */}
        <p className="text-xs text-slate-500">
          Location names are resolved automatically: <em>India</em> → all major Indian airports,{" "}
          <em>Ahmedabad</em> → AMD, <em>Japan</em> → NRT, HND, KIX …
          You can also type IATA codes directly or combine them: <em>TYO, SHA</em>.
        </p>

        {error && (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-600">{error}</p>
        )}

        <div className="flex justify-end gap-2 pt-1">
          <Button type="button" variant="secondary" onClick={onClose}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={saving}>
            Create profile
          </Button>
        </div>
      </form>
    </Modal>
  );
}

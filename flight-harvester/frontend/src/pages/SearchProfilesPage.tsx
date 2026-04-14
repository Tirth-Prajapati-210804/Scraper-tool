import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Plus, RefreshCw, Trash2 } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";
import {
  deleteSearchProfile,
  listSearchProfiles,
  updateSearchProfile,
} from "../api/search-profiles";
import { triggerGroupCollection } from "../api/collection";
import { SearchProfileForm } from "../components/SearchProfileForm";
import { Button } from "../components/ui/Button";
import { Card } from "../components/ui/Card";
import { ConfirmDialog } from "../components/ui/ConfirmDialog";
import { useToast } from "../context/ToastContext";
import type { SearchProfile } from "../types/search-profile";
import { usePageTitle } from "../utils/usePageTitle";

export function SearchProfilesPage() {
  usePageTitle("Search Profiles");
  const qc = useQueryClient();
  const { showToast } = useToast();
  const [createOpen, setCreateOpen] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<SearchProfile | null>(null);

  const { data: profiles = [], isLoading } = useQuery({
    queryKey: ["search-profiles"],
    queryFn: () => listSearchProfiles(false),
  });

  const deleteMutation = useMutation({
    mutationFn: (id: string) => deleteSearchProfile(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["search-profiles"] });
      showToast("Profile deleted", "success");
      setDeleteTarget(null);
    },
    onError: () => showToast("Failed to delete profile", "error"),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      updateSearchProfile(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["search-profiles"] }),
    onError: () => showToast("Update failed", "error"),
  });

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">Search Profiles</h1>
          <p className="mt-0.5 text-sm text-slate-500">
            Each profile defines one or more flight legs to track continuously.
          </p>
        </div>
        <Button variant="primary" onClick={() => setCreateOpen(true)}>
          <Plus className="mr-1.5 h-4 w-4" />
          New profile
        </Button>
      </div>

      {isLoading && (
        <div className="text-sm text-slate-500">Loading profiles…</div>
      )}

      {!isLoading && profiles.length === 0 && (
        <Card className="py-12 text-center">
          <p className="text-slate-500">No search profiles yet.</p>
          <p className="mt-1 text-sm text-slate-400">
            Create one to start tracking flight prices automatically.
          </p>
          <Button
            variant="primary"
            className="mt-4"
            onClick={() => setCreateOpen(true)}
          >
            <Plus className="mr-1.5 h-4 w-4" />
            Create your first profile
          </Button>
        </Card>
      )}

      <div className="space-y-4">
        {profiles.map((profile) => (
          <ProfileCard
            key={profile.id}
            profile={profile}
            onToggle={(is_active) =>
              toggleMutation.mutate({ id: profile.id, is_active })
            }
            onDelete={() => setDeleteTarget(profile)}
          />
        ))}
      </div>

      <SearchProfileForm open={createOpen} onClose={() => setCreateOpen(false)} />

      <ConfirmDialog
        open={!!deleteTarget}
        onClose={() => setDeleteTarget(null)}
        title="Delete profile"
        message={`Delete "${deleteTarget?.name}"? All collected prices for this profile will be permanently removed.`}
        confirmLabel="Delete"
        onConfirm={() => deleteTarget && deleteMutation.mutate(deleteTarget.id)}
        loading={deleteMutation.isPending}
      />
    </div>
  );
}

// ── Profile card ──────────────────────────────────────────────────────────────

function ProfileCard({
  profile,
  onToggle,
  onDelete,
}: {
  profile: SearchProfile;
  onToggle: (active: boolean) => void;
  onDelete: () => void;
}) {
  const { showToast } = useToast();
  const [triggering, setTriggering] = useState(false);

  async function handleTrigger() {
    setTriggering(true);
    try {
      // Re-use the existing collection trigger endpoint
      await triggerGroupCollection(profile.id);
      showToast("Collection started", "success");
    } catch {
      showToast("Failed to trigger collection", "error");
    } finally {
      setTriggering(false);
    }
  }

  return (
    <Card className="p-4">
      <div className="flex items-start justify-between gap-4">
        {/* Left: name + legs summary */}
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-2">
            <Link
              to={`/search-profiles/${profile.id}`}
              className="text-base font-semibold text-slate-900 hover:text-brand-600 truncate"
            >
              {profile.name}
            </Link>
            <span
              className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                profile.is_active
                  ? "bg-green-100 text-green-700"
                  : "bg-slate-100 text-slate-500"
              }`}
            >
              {profile.is_active ? "Active" : "Paused"}
            </span>
          </div>

          <div className="mt-2 space-y-1">
            {profile.legs.map((leg, idx) => (
              <div key={leg.id} className="flex items-center gap-2 text-sm text-slate-600">
                <span className="w-5 text-xs text-slate-400 font-mono">
                  L{idx + 1}
                </span>
                <span className="font-medium">{leg.origin_query}</span>
                <span className="text-slate-400">→</span>
                <span className="font-medium">{leg.destination_query}</span>
                {leg.resolved_origins.length > 0 && (
                  <span className="text-xs text-slate-400">
                    ({leg.resolved_origins.join(", ")} → {leg.resolved_destinations.join(", ")})
                  </span>
                )}
                {leg.min_halt_hours !== null && idx < profile.legs.length - 1 && (
                  <span className="text-xs text-amber-600">
                    · wait {leg.min_halt_hours}h+
                  </span>
                )}
              </div>
            ))}
          </div>

          <p className="mt-2 text-xs text-slate-400">
            {profile.days_ahead} days ahead · {profile.legs.length} leg
            {profile.legs.length !== 1 ? "s" : ""}
          </p>
        </div>

        {/* Right: actions */}
        <div className="flex items-center gap-2 shrink-0">
          <Button
            variant="secondary"
            onClick={handleTrigger}
            loading={triggering}
          >
            <RefreshCw className="h-3.5 w-3.5" />
          </Button>
          <Button
            variant="secondary"
            onClick={() => onToggle(!profile.is_active)}
          >
            {profile.is_active ? "Pause" : "Resume"}
          </Button>
          <Button
            variant="secondary"
            onClick={onDelete}
            className="text-red-500 hover:bg-red-50"
          >
            <Trash2 className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>
    </Card>
  );
}

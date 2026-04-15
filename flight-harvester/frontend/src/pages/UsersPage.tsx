import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { UserCheck, UserX, Users } from "lucide-react";
import { deactivateUser, listUsers, reactivateUser } from "../api/users";
import { Card } from "../components/ui/Card";
import { Skeleton } from "../components/ui/Skeleton";
import { useAuth } from "../context/AuthContext";
import { useToast } from "../context/ToastContext";
import type { UserAdmin } from "../types/auth";
import { usePageTitle } from "../utils/usePageTitle";

export function UsersPage() {
  usePageTitle("User Management");
  const { user: currentUser } = useAuth();
  const { showToast } = useToast();
  const qc = useQueryClient();

  const { data: users, isLoading } = useQuery({
    queryKey: ["users"],
    queryFn: listUsers,
  });

  const deactivateMut = useMutation({
    mutationFn: (id: string) => deactivateUser(id),
    onSuccess: () => {
      showToast("User deactivated", "success");
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => showToast("Failed to deactivate user", "error"),
  });

  const reactivateMut = useMutation({
    mutationFn: (id: string) => reactivateUser(id),
    onSuccess: () => {
      showToast("User reactivated", "success");
      qc.invalidateQueries({ queryKey: ["users"] });
    },
    onError: () => showToast("Failed to reactivate user", "error"),
  });

  // Redirect non-admins — the API will also return 403, but show a friendly message
  if (currentUser && currentUser.role !== "admin") {
    return (
      <div className="py-16 text-center text-slate-400">
        You don't have permission to view this page.
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center gap-3">
        <Users className="h-6 w-6 text-brand-600" />
        <h1 className="text-xl font-bold text-slate-900">User Management</h1>
      </div>

      <Card className="p-5">
        {isLoading ? (
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-12" />
            ))}
          </div>
        ) : !users?.length ? (
          <p className="text-center text-sm text-slate-400 py-8">No users found.</p>
        ) : (
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-200">
                <th className="pb-2 text-left font-medium text-slate-600">Name</th>
                <th className="pb-2 text-left font-medium text-slate-600">Email</th>
                <th className="pb-2 text-left font-medium text-slate-600">Role</th>
                <th className="pb-2 text-left font-medium text-slate-600">Status</th>
                <th className="pb-2 text-left font-medium text-slate-600">Joined</th>
                <th className="pb-2 text-right font-medium text-slate-600">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {users.map((u: UserAdmin) => (
                <tr key={u.id} className="py-2">
                  <td className="py-2.5 pr-4 font-medium text-slate-800">
                    {u.full_name}
                    {u.id === currentUser?.id && (
                      <span className="ml-2 text-xs text-slate-400">(you)</span>
                    )}
                  </td>
                  <td className="py-2.5 pr-4 text-slate-600">{u.email}</td>
                  <td className="py-2.5 pr-4">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        u.role === "admin"
                          ? "bg-purple-100 text-purple-700"
                          : "bg-slate-100 text-slate-600"
                      }`}
                    >
                      {u.role}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4">
                    <span
                      className={`rounded-full px-2 py-0.5 text-xs font-medium ${
                        u.is_active
                          ? "bg-green-100 text-green-700"
                          : "bg-red-100 text-red-600"
                      }`}
                    >
                      {u.is_active ? "Active" : "Inactive"}
                    </span>
                  </td>
                  <td className="py-2.5 pr-4 text-slate-500">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  <td className="py-2.5 text-right">
                    {u.id !== currentUser?.id && (
                      u.is_active ? (
                        <button
                          onClick={() => deactivateMut.mutate(u.id)}
                          disabled={deactivateMut.isPending}
                          className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium text-red-600 hover:bg-red-50 disabled:opacity-50"
                          title="Deactivate user"
                        >
                          <UserX className="h-3.5 w-3.5" />
                          Deactivate
                        </button>
                      ) : (
                        <button
                          onClick={() => reactivateMut.mutate(u.id)}
                          disabled={reactivateMut.isPending}
                          className="inline-flex items-center gap-1 rounded-lg px-2.5 py-1 text-xs font-medium text-green-600 hover:bg-green-50 disabled:opacity-50"
                          title="Reactivate user"
                        >
                          <UserCheck className="h-3.5 w-3.5" />
                          Reactivate
                        </button>
                      )
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </div>
  );
}

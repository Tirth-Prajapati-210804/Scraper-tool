import {
  History,
  LayoutDashboard,
  LogOut,
  Plane,
  Search,
  Table,
  Users,
} from "lucide-react";
import { NavLink } from "react-router-dom";
import { useAuth } from "../../context/AuthContext";
import { cn } from "../../utils/cn";

const navItems = [
  { to: "/", icon: LayoutDashboard, label: "Dashboard" },
  { to: "/search-profiles", icon: Search, label: "Search Profiles" },
  { to: "/explorer", icon: Table, label: "Data Explorer" },
  { to: "/logs", icon: History, label: "Collection Logs" },
];

export function Sidebar() {
  const { user, logout } = useAuth();
  const isAdmin = user?.role === "admin";

  return (
    <aside className="flex w-56 flex-shrink-0 flex-col border-r border-slate-200 bg-white">
      {/* Logo */}
      <div className="flex h-14 items-center gap-2 border-b border-slate-200 px-4">
        <div className="flex h-7 w-7 items-center justify-center rounded-lg bg-brand-600">
          <Plane className="h-4 w-4 text-white" />
        </div>
        <span className="text-sm font-semibold text-slate-800">
          Flight Data Scrapper
        </span>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-0.5 p-2 pt-3">
        {navItems.map(({ to, icon: Icon, label }) => (
          <NavLink
            key={to}
            to={to}
            end={to === "/"}
            className={({ isActive }) =>
              cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-brand-50 text-brand-700"
                  : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
              )
            }
          >
            <Icon className="h-4 w-4 flex-shrink-0" />
            {label}
          </NavLink>
        ))}

        {/* Admin-only section */}
        {isAdmin && (
          <>
            <div className="mt-3 mb-1 px-3 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
              Admin
            </div>
            <NavLink
              to="/users"
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-brand-50 text-brand-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                )
              }
            >
              <Users className="h-4 w-4 flex-shrink-0" />
              Users
            </NavLink>
          </>
        )}
      </nav>

      {/* User info + logout */}
      <div className="border-t border-slate-200 p-3">
        <div className="mb-1 truncate px-2 text-xs font-medium text-slate-700">
          {user?.full_name}
        </div>
        <div className="mb-2 flex items-center gap-1.5 px-2">
          <span className="truncate text-xs text-slate-400">{user?.email}</span>
          {isAdmin && (
            <span className="shrink-0 rounded-full bg-purple-100 px-1.5 py-0.5 text-[10px] font-medium text-purple-700">
              admin
            </span>
          )}
        </div>
        <button
          onClick={logout}
          className="flex w-full items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-600 transition-colors hover:bg-red-50 hover:text-red-600"
        >
          <LogOut className="h-4 w-4" />
          Sign out
        </button>
      </div>
    </aside>
  );
}

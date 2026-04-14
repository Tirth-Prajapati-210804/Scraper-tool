import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter, Navigate, Outlet, Route, Routes } from "react-router-dom";
import { AppLayout } from "./components/layout/AppLayout";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { AuthProvider } from "./context/AuthContext";
import { ToastProvider } from "./context/ToastContext";
import { CollectionLogsPage } from "./pages/CollectionLogsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { DataExplorerPage } from "./pages/DataExplorerPage";
import { LoginPage } from "./pages/LoginPage";
import { RouteGroupDetailPage } from "./pages/RouteGroupDetailPage";
import { SearchProfilesPage } from "./pages/SearchProfilesPage";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <BrowserRouter>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <ToastProvider>
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route
                element={
                  <ProtectedRoute>
                    <AppLayout>
                      <Outlet />
                    </AppLayout>
                  </ProtectedRoute>
                }
              >
                <Route path="/" element={<DashboardPage />} />
                <Route path="/search-profiles" element={<SearchProfilesPage />} />
                <Route path="/route-groups/:id" element={<RouteGroupDetailPage />} />
                <Route path="/explorer" element={<DataExplorerPage />} />
                <Route path="/logs" element={<CollectionLogsPage />} />
              </Route>
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </ToastProvider>
        </AuthProvider>
      </QueryClientProvider>
    </BrowserRouter>
  );
}

import axios from "axios";

// In Docker, VITE_API_BASE_URL is "" so axios uses relative URLs (proxied by nginx).
// In local dev it is "http://localhost:8000" (set in frontend/.env).
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 30_000,
});

// Attach JWT token to every request
api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Auto-redirect to login on 401
api.interceptors.response.use(
  (res) => res,
  (err) => {
    if (
      err.response?.status === 401 &&
      window.location.pathname !== "/login"
    ) {
      localStorage.removeItem("token");
      window.location.href = "/login";
    }
    return Promise.reject(err);
  },
);

import axios from "axios";

// ---------------------------------------------------------------------------
// Types (mirroring backend Pydantic schemas)
// ---------------------------------------------------------------------------

export interface Tag {
  id: string;
  name: string;
}

export type SortBy = "date_added" | "price" | "brand";
export type SortDir = "asc" | "desc";

export interface Product {
  id: string;
  url: string;
  title: string | null;
  image_url: string | null;
  category: string | null;
  platform: string | null;
  brand: string | null;
  current_price: number | null;
  currency: string;
  in_stock: boolean | null;
  tags: Tag[];
  created_at: string;
  updated_at: string;
}

export interface FieldDebug {
  value: number | string | null;
  source: string;
  selector: string | null;
}

export interface ParseDebug {
  layers_run: string[];
  fields: Record<string, FieldDebug>;
}

export interface ParsePreview {
  url: string;
  title: string | null;
  price: number | null;
  currency: string;
  image_url: string | null;
  category: string | null;
  platform: string;
  is_complete: boolean;
  debug?: ParseDebug;
}

export interface PricePoint {
  id: number;
  price: number;
  currency: string;
  scraped_at: string;
}

export interface WatchConfig {
  id: string;
  product_id: string;
  alert_on_drop_pct: number;
  is_active: boolean;
  notify_on_restock: boolean;
  last_checked_at: string | null;
  created_at: string;
}

export interface WatchConfigIn {
  alert_on_drop_pct?: number;
  is_active?: boolean;
  notify_on_restock?: boolean;
}

export interface Settings {
  notify_email: string | null;
  check_interval_hours: number;
  alert_on_rise: boolean;
  updated_at: string;
}

export interface SettingsIn {
  notify_email?: string | null;
  check_interval_hours?: number;
  alert_on_rise?: boolean;
}

export interface CookieStatusOut {
  domain: string;
  status: "none" | "valid" | "expired";
  cookie_count: number | null;
  updated_at: string | null;
}

// ---------------------------------------------------------------------------
// Axios instance
// ---------------------------------------------------------------------------

const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL ?? "http://localhost:8000",
  headers: { "Content-Type": "application/json" },
});

// ---------------------------------------------------------------------------
// Products
// ---------------------------------------------------------------------------

export const getProducts = (params?: {
  category?: string;
  tag?: string;
  sort_by?: SortBy;
  sort_dir?: SortDir;
}) => api.get<Product[]>("/api/products", { params });

export const getTags = () =>
  api.get<string[]>("/api/tags");

export const deleteTag = (name: string) =>
  api.delete(`/api/tags/${encodeURIComponent(name)}`);

export const getProduct = (id: string) =>
  api.get<Product>(`/api/products/${id}`);

export const createProduct = (url: string, tags: string[] = [], saveAnyway = false) =>
  api.post<Product>("/api/products", { url, tags, save_anyway: saveAnyway });

export const deleteProduct = (id: string) =>
  api.delete(`/api/products/${id}`);

export const updateProductTags = (id: string, tags: string[]) =>
  api.patch<Product>(`/api/products/${id}/tags`, { tags });

export const updateProductImage = (id: string, imageUrl: string | null) =>
  api.patch<Product>(`/api/products/${id}/image`, { image_url: imageUrl });

export const suggestTags = (id: string) =>
  api.post<{ suggested_tags: string[] }>(`/api/products/${id}/suggest-tags`);

// ---------------------------------------------------------------------------
// Parse preview
// ---------------------------------------------------------------------------

export const parseUrl = (url: string) =>
  api.post<ParsePreview>("/api/parse", { url });

// ---------------------------------------------------------------------------
// Price history
// ---------------------------------------------------------------------------

export const getPriceHistory = (id: string, days = 30) =>
  api.get<PricePoint[]>(`/api/products/${id}/prices`, { params: { days } });

// ---------------------------------------------------------------------------
// Watch config
// ---------------------------------------------------------------------------

export const getWatchConfig = (id: string) =>
  api.get<WatchConfig>(`/api/products/${id}/watch`);

export const upsertWatchConfig = (id: string, data: WatchConfigIn) =>
  api.put<WatchConfig>(`/api/products/${id}/watch`, data);

// ---------------------------------------------------------------------------
// Manual price check
// ---------------------------------------------------------------------------

export const triggerPriceCheck = (id: string) =>
  api.post<{ status: string; task_id: string }>(`/api/products/${id}/check`);

// ---------------------------------------------------------------------------
// Cookies
// ---------------------------------------------------------------------------

export const importCookies = (domain: string, curl: string) =>
  api.put<CookieStatusOut>(`/api/domains/${domain}/cookies`, { curl });

export const getCookieStatus = (domain: string) =>
  api.get<CookieStatusOut>(`/api/domains/${domain}/cookies`);

// ---------------------------------------------------------------------------
// Settings
// ---------------------------------------------------------------------------

export const getSettings = () =>
  api.get<Settings>("/api/settings");

export const updateSettings = (data: SettingsIn) =>
  api.put<Settings>("/api/settings", data);

// ---------------------------------------------------------------------------
// Dev helpers (DEBUG mode only)
// ---------------------------------------------------------------------------

export interface TestCaseExpect {
  price?: string | null;
  title?: string | null;
  image?: string | null;
  brand?: string | null;
  in_stock?: string | null;
}

export interface TestCaseIn {
  url: string;
  label?: string;
  fetch?: string;
  expect?: TestCaseExpect;
  note?: string;
}

export const addTestCase = (data: TestCaseIn) =>
  api.post("/api/dev/test-cases", data);

/**
 * API Client
 * ===========
 * All backend communication.
 *
 * Endpoints:
 *   GET  /folders               → folder list
 *   GET  /folders/{id}          → folder detail with all images
 *   POST /generate              → submit generation (prompt_id only, no text)
 *   GET  /generation/{task_id}  → poll status
 *   GET  /gallery               → completed generations
 *
 * Security: prompt text is NEVER sent from the frontend.
 * The frontend only sends prompt_id (an opaque backend reference).
 */

import axios from "axios";
import type {
  FoldersResponse,
  FolderDetail,
  GenerateResponse,
  GenerationStatus,
  GalleryResponse,
} from "@/types";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

const api = axios.create({
  baseURL: API_BASE_URL,
  timeout: 120_000,
});

// ---------------------------------------------------------------------------
// Folders (raw backend)
// ---------------------------------------------------------------------------

export async function getFolders(): Promise<FoldersResponse> {
  const res = await api.get<FoldersResponse>("/folders");
  return res.data;
}

export async function getFolder(folderId: string): Promise<FolderDetail> {
  const res = await api.get<FolderDetail>(`/folders/${folderId}`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Styles  (Gallery.tsx adapter — maps /folders to the shape StyleCard expects)
// ---------------------------------------------------------------------------

export interface StylesParams {
  page?: number;
  limit?: number;
  search?: string;
  category?: string;
}

export interface StyleCard {
  image_url: string;
  /**
   * IMPORTANT: this is the real backend prompt_id (e.g. "folder-id::p0").
   * It is passed directly to POST /generate.  Do NOT invent a synthetic id.
   */
  prompt_id: string;
}

export interface Style {
  id: string;
  title: string;
  category: string;
  thumbnail?: string;
  image_url?: string;
  card_count?: number;
  cards?: StyleCard[];
}

export interface StylesResponse {
  items: Style[];
  total: number;
}

/**
 * getStyles() — maps GET /folders into the shape Gallery.tsx expects.
 *
 * Each card in the returned Style carries the real backend prompt_id,
 * so Gallery.tsx can pass it straight to generateSimilarImage()/
 * generateSameImage() without
 * any synthetic ID construction.
 */
export async function getStyles(
  params: StylesParams = {}
): Promise<StylesResponse> {
  const res = await api.get<FoldersResponse>("/folders");
  const folders = res.data.items ?? [];

  let items: Style[] = folders.map((f) => ({
    id: f.folder_id,
    title: f.title,
    category: f.title.split(" ")[0].toLowerCase(),
    thumbnail: f.cover_image ?? undefined,
    image_url: f.cover_image ?? undefined,
    card_count: f.prompt_count,
    // ← each card carries the REAL prompt_id from the backend
    cards: (f.preview_images ?? []).map((pi) => ({
      image_url: pi.image_url,
      prompt_id: pi.prompt_id,   // e.g. "hollywood-...-fc6a51::p0"
    })),
  }));

  if (params.search) {
    const q = params.search.toLowerCase();
    items = items.filter((s) => s.title.toLowerCase().includes(q));
  }

  if (params.category && params.category !== "all") {
    items = items.filter((s) =>
      s.category.toLowerCase().includes(params.category!.toLowerCase())
    );
  }

  return { items, total: items.length };
}

// ---------------------------------------------------------------------------
// Categories  (CategoryFilter.tsx adapter)
// ---------------------------------------------------------------------------

export interface CategoriesResponse {
  items: string[];
}

export async function getCategories(): Promise<CategoriesResponse> {
  const res = await api.get<FoldersResponse>("/folders");
  const folders = res.data.items ?? [];
  const categorySet = new Set<string>();
  folders.forEach((f) => {
    const first = f.title.split(" ")[0];
    if (first) categorySet.add(first);
  });
  return { items: Array.from(categorySet) };
}

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------

/**
 * generateSimilarImage() — submits prompt_id + user image to
 * POST /generate/similar. The default pipeline: restyles the user's own
 * photo toward the prompt.
 *
 * generateSameImage() — submits prompt_id + user image to
 * POST /generate/same. Keeps the style's sample background/outfit/pose
 * and only swaps in the uploaded photo's face.
 *
 * These are deliberately two separate functions hitting two separate
 * endpoints — not one function branching on a boolean — so each mode's
 * request shape can evolve independently.
 *
 * The promptId here must be the real backend prompt_id (e.g. "folder::p0").
 * It is NEVER the prompt text — that lives only on the server.
 */
export async function generateSimilarImage(
  promptId: string,
  userImage: File
): Promise<GenerateResponse & { image_url?: string }> {
  const form = new FormData();
  form.append("prompt_id", promptId);   // opaque ID, no text
  form.append("user_image", userImage);

  const res = await api.post<GenerateResponse>("/generate/similar", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function generateSameImage(
  promptId: string,
  userImage: File
): Promise<GenerateResponse & { image_url?: string }> {
  const form = new FormData();
  form.append("prompt_id", promptId);   // opaque ID, no text
  form.append("user_image", userImage);

  const res = await api.post<GenerateResponse>("/generate/same", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

/** Aliases used by newer components */
export const submitSimilarGeneration = generateSimilarImage;
export const submitSameGeneration = generateSameImage;

/**
 * generateImage() — single dispatcher used by app/page.tsx's two buttons.
 *
 * sameBackground = false → POST /generate/similar (restyle the user's own
 *                           photo toward the prompt)
 * sameBackground = true  → POST /generate/same (keep the style's sample
 *                           image's background/outfit/pose untouched and
 *                           face-swap in the user's uploaded photo)
 *
 * This is just a thin router over the two mode-specific functions above —
 * it does not duplicate any request logic.
 */
export async function generateImage(
  promptId: string,
  userImage: File,
  sameBackground: boolean = false
): Promise<GenerateResponse & { image_url?: string }> {
  return sameBackground
    ? generateSameImage(promptId, userImage)
    : generateSimilarImage(promptId, userImage);
}

export async function getGenerationStatus(
  taskId: string
): Promise<GenerationStatus> {
  const res = await api.get<GenerationStatus>(`/generation/${taskId}`);
  return res.data;
}

// ---------------------------------------------------------------------------
// Gallery
// ---------------------------------------------------------------------------

export async function getGallery(page = 1): Promise<GalleryResponse> {
  const res = await api.get<GalleryResponse>("/gallery", {
    params: { page, limit: 20 },
  });
  return res.data;
}

// ---------------------------------------------------------------------------
// URL resolver
// ---------------------------------------------------------------------------

/**
 * Resolve the best URL to display.
 * Priority: Cloudinary → original HTTP URL → local /static/ path
 */
export function resolveImageUrl(
  cloudinaryUrl?: string | null,
  originalUrl?: string | null,
  fallbackPath?: string
): string {
  if (cloudinaryUrl) return cloudinaryUrl;
  if (originalUrl) {
    return originalUrl.startsWith("http")
      ? originalUrl
      : `${API_BASE_URL}${originalUrl}`;
  }
  if (fallbackPath) {
    return fallbackPath.startsWith("http")
      ? fallbackPath
      : `${API_BASE_URL}${fallbackPath}`;
  }
  return "";
}

export function getImageUrl(path: string): string {
  return resolveImageUrl(null, null, path);
}

export default api;
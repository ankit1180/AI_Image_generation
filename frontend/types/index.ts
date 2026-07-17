/**
 * Frontend Types
 * ==============
 * Matches backend API responses exactly.
 *
 * Security rule: prompt text is NEVER present in any of these types.
 * The frontend only works with: folder info, image URLs,
 * prompt_id (opaque), generation status, and result URLs.
 */

// ---------------------------------------------------------------------------
// Preview image inside a folder
// ---------------------------------------------------------------------------

export interface PreviewImage {
  /** Opaque ID submitted to POST /generate – NOT the prompt text */
  prompt_id: string;
  index: number;
  /** Original source URL – always preserved, never replaced */
  original_url: string;
  /** Cloudinary URL if uploaded, null otherwise */
  cloudinary_url: string | null;
  public_id: string | null;
  uploaded: boolean;
  /** Convenience alias: cloudinary_url ?? original_url */
  image_url: string;
}

// ---------------------------------------------------------------------------
// Folders
// ---------------------------------------------------------------------------

export interface FolderSummary {
  folder_id: string;
  title: string;
  cover_image: string | null;
  prompt_count: number;
  /** First 4 preview images shown on the folder card */
  preview_images: PreviewImage[];
}

export interface FolderDetail {
  folder_id: string;
  title: string;
  cover_image: string | null;
  prompt_count: number;
  /** All preview images in this folder */
  images: PreviewImage[];
}

export interface FoldersResponse {
  total: number;
  items: FolderSummary[];
}

// ---------------------------------------------------------------------------
// Generation
// ---------------------------------------------------------------------------

/**
 * Generation mode:
 *  - "similar" → the original, unmodified generation pipeline (default).
 *                Unchanged from before this option existed.
 *  - "same"    → face-swap-only. Keeps the sample image's pose/background
 *                close to unchanged and mainly replaces the person with
 *                the user's uploaded face.
 */
export type GenerationMode = "similar" | "same";

/** Response from POST /generate */
export interface GenerateResponse {
  task_id: string;
  /** ID only – never the prompt text */
  prompt_id: string;
  mode: GenerationMode;
  status: "queued" | "processing" | "completed" | "failed";
  message: string;
}

/** Response from GET /generation/{task_id} */
export interface GenerationStatus {
  task_id: string;
  prompt_id: string;
  mode?: GenerationMode;
  status: "queued" | "processing" | "completed" | "failed";
  progress: number;
  image_url: string | null;
  cloudinary_url: string | null;
  uploaded: boolean;
  error: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Gallery
// ---------------------------------------------------------------------------

export interface GalleryImage {
  task_id: string;
  image_url: string;
  original_url: string | null;
  cloudinary_url: string | null;
  uploaded: boolean;
  status: string;
  created_at: string;
}

export interface GalleryResponse {
  page: number;
  limit: number;
  total: number;
  items: GalleryImage[];
}

// ---------------------------------------------------------------------------
// UI state
// ---------------------------------------------------------------------------

/** The preview image the user has selected to generate from */
export interface SelectedPreview {
  /** Submitted to backend – never the prompt text */
  prompt_id: string;
  folder_title: string;
  /** Display URL for the selected thumbnail */
  image_url: string;
  index: number;
}
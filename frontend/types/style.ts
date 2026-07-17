/**
 * types/style.ts
 * ==============
 * UI-layer types used by Gallery, RecentGallery, and page.tsx.
 * These complement (and no longer conflict with) types/index.ts.
 */

// ---------------------------------------------------------------------------
// Gallery / Style card
// ---------------------------------------------------------------------------

export interface StyleCard {
  image_url: string;
  prompt_id?: string;
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

// ---------------------------------------------------------------------------
// Selected style (what the user picks before uploading)
// ---------------------------------------------------------------------------

export interface SelectedStyle {
  id: string;        // prompt_id or folder_id
  title: string;     // human-readable label shown in the UI
  thumbnail?: string;
}

// ---------------------------------------------------------------------------
// Gallery image (from GET /gallery)
// ---------------------------------------------------------------------------

export interface GalleryImage {
  task_id: string;
  image_url: string;
  original_url?: string | null;
  cloudinary_url?: string | null;
  uploaded?: boolean;
  status?: string;
  created_at: string;
  /** style_id is returned by the backend when present */
  style_id?: string;
  /** prompt text is NOT returned by the API; this is undefined in practice */
  prompt?: string;
}

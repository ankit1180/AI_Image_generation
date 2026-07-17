"use client";

import { useMemo, useState } from "react";

import CategoryFilter from "@/components/CategoryFilter";
import Gallery from "@/components/Gallery";
import ResultModal from "@/components/ResultModal";
import SearchBar from "@/components/SearchBar";
import UploadBox from "@/components/UploadBox";
import Hero from "@/components/Hero";
import Stats from "@/components/Stats";
import RecentGallery from "@/components/RecentGallery";
import {
  generateImage,
  getGenerationStatus,
} from "@/lib/api";

import type { SelectedStyle } from "@/types/style";

export default function HomePage() {
  // ---------------------------------------
  // Search & Filters
  // ---------------------------------------

  const [search, setSearch] = useState("");

  const [category, setCategory] = useState("All");

  // ---------------------------------------
  // Selected Style
  // ---------------------------------------

  const [selectedStyle, setSelectedStyle] =
    useState<SelectedStyle | null>(null);

  // ---------------------------------------
  // Uploaded Image
  // ---------------------------------------

  const [selectedFile, setSelectedFile] =
    useState<File | null>(null);

  // ---------------------------------------
  // Generation
  // ---------------------------------------

  const [loading, setLoading] = useState(false);

  const [generatedImage, setGeneratedImage] =
    useState("");

  const [generationStatus, setGenerationStatus] =
    useState("");

  const [generationProgress, setGenerationProgress] =
    useState(0);

  const [generationError, setGenerationError] =
    useState("");

  const [refreshTrigger, setRefreshTrigger] =
    useState(0);

  // Which button triggered the in-flight generation ("normal" |
  // "same-background"), so the UI can show the right loading label
  // on the right button.
  const [activeMode, setActiveMode] =
    useState<"normal" | "same-background" | null>(null);

  const canGenerate = useMemo(() => {
    return (
      selectedStyle !== null &&
      selectedFile !== null &&
      !loading
    );
  }, [selectedStyle, selectedFile, loading]);

  async function handleGenerate(sameBackground: boolean = false) {
    if (!selectedStyle || !selectedFile) {
      return;
    }

    try {
      setLoading(true);
      setActiveMode(sameBackground ? "same-background" : "normal");
      setGenerationError("");
      setGenerationStatus("Uploading image");
      setGenerationProgress(5);

      const response = await generateImage(
        selectedStyle.id,
        selectedFile,
        sameBackground
      );

      setGenerationStatus("Queued");
      setGenerationProgress(10);

      if (response.image_url) {
        setGeneratedImage(response.image_url);
        setGenerationStatus("Completed");
        setGenerationProgress(100);
        setRefreshTrigger((prev) => prev + 1);
        return;
      }

      // Poll for up to 4 minutes (120 × 2 s)
      let attempts = 0;
      const MAX_ATTEMPTS = 300;

      while (attempts < MAX_ATTEMPTS) {
        attempts += 1;

        await new Promise((resolve) =>
          setTimeout(resolve, 2000)
        );

        const status = await getGenerationStatus(
          response.task_id
        );

        // Progress should never move backward in the UI, even if the
        // backend still reports an earlier snapshot (e.g. the task record
        // was created with progress=5 but the Celery worker hasn't picked
        // it up yet when we poll, so it can briefly report less than the
        // optimistic value we already set after submission).
        setGenerationProgress((prev) =>
          Math.max(prev, status.progress ?? 0)
        );

        // Same idea for the label: don't fall back to "queued" once we've
        // already shown a later-stage status.
        setGenerationStatus((prev) => {
          const nextLabel =
            status.status === "processing"
              ? "Generating image"
              : status.status;
          if (prev === "Generating image" && nextLabel === "queued") {
            return prev;
          }
          return nextLabel;
        });

        if (status.image_url) {
          setGeneratedImage(status.image_url);
          setGenerationStatus("Completed");
          setGenerationProgress(100);
          setRefreshTrigger((prev) => prev + 1);
          return;
        }

        if (
          status.status === "failed"
        ) {
          throw new Error(
            status.error ?? "Generation failed."
          );
        }
      }

      // ⚠️  Timeout: 4 minutes elapsed with no result
      throw new Error(
        "Generation timed out after 10 minutes. Please try again."
      );
    } catch (error) {
      console.error(error);

      setGenerationError(
        error instanceof Error
          ? error.message
          : "Failed to generate image."
      );
    } finally {
      setLoading(false);
      setActiveMode(null);
      setGenerationStatus("");
      setGenerationProgress(0);
    }
  }

  return (
    <div className="space-y-16 md:space-y-24">
      {/* Hero section */}
      <Hero />

      {/* Stats section */}
      <Stats />

      {/* Style selector title */}
      <div id="styles" className="scroll-mt-24">
        <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between border-b border-white/5 pb-6">
          <div>
            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white font-outfit">
              Choose a Transformation Style
            </h2>
            <p className="mt-2 text-sm md:text-base text-gray-400">
              Select one of our premium AI filters to apply to your uploaded image.
            </p>
          </div>

          {selectedStyle && (
            <span className="self-start md:self-auto inline-flex items-center gap-1.5 rounded-full bg-indigo-500/10 px-4 py-2 text-xs md:text-sm font-semibold text-indigo-300 ring-1 ring-inset ring-indigo-500/30 backdrop-blur-sm animate-fade-in">
              <span className="h-1.5 w-1.5 rounded-full bg-indigo-400 animate-ping" />
              Selected Style: {selectedStyle.title}
            </span>
          )}
        </div>
      </div>

      {/* Search and Filters */}
      <div className="flex flex-col gap-4 md:flex-row md:items-center">
        <div className="flex-1">
          <SearchBar
            value={search}
            onChange={setSearch}
          />
        </div>
        <div className="md:w-auto">
          <CategoryFilter
            selected={category}
            setSelected={setCategory}
          />
        </div>
      </div>

      {/* Gallery */}
      <Gallery
        search={search}
        category={category}
        selectedStyle={selectedStyle}
        onSelect={setSelectedStyle}
      />

      {/* Upload + Generate */}
      <section id="generate" className="grid gap-8 lg:grid-cols-2 scroll-mt-24">
        <div className="glass-panel rounded-3xl p-6 md:p-8 space-y-6 relative overflow-hidden">
          <div className="absolute top-0 right-0 h-40 w-40 bg-indigo-600/5 rounded-full blur-3xl pointer-events-none" />
          
          <div>
            <h3 className="text-xl md:text-2xl font-bold text-white font-outfit">
              1. Upload Your Image
            </h3>
            <p className="text-sm text-gray-400 mt-1">
              Select a JPG, PNG, or WEBP image up to 10MB to transform.
            </p>
          </div>

          <UploadBox
            file={selectedFile}
            onChange={setSelectedFile}
          />
        </div>

        <div className="glass-panel rounded-3xl p-6 md:p-8 flex flex-col justify-between relative overflow-hidden">
          <div className="absolute top-0 right-0 h-40 w-40 bg-purple-600/5 rounded-full blur-3xl pointer-events-none" />
          
          <div className="space-y-6">
            <div>
              <h3 className="text-xl md:text-2xl font-bold text-white font-outfit">
                2. Process Transformation
              </h3>
              <p className="text-sm text-gray-400 mt-1">
                Verify your parameters and trigger the AI generation pipeline.
              </p>
            </div>

            <div className="rounded-2xl bg-white/5 p-5 border border-white/5 space-y-3">
              <div className="flex items-center justify-between text-sm">
                <span className="font-medium text-gray-400">Selected Style</span>
                <span className={`font-semibold ${selectedStyle ? "text-indigo-400" : "text-gray-600"}`}>
                  {selectedStyle?.title ?? "None selected"}
                </span>
              </div>

              <div className="flex items-center justify-between text-sm border-t border-white/5 pt-3">
                <span className="font-medium text-gray-400">Source Image</span>
                <span className={`font-semibold max-w-[200px] truncate ${selectedFile ? "text-green-400" : "text-gray-600"}`}>
                  {selectedFile?.name ?? "None uploaded"}
                </span>
              </div>
            </div>

            {(loading || generationStatus) && (
              <div
                className="space-y-3 rounded-2xl border border-indigo-500/10 bg-indigo-950/20 p-5"
                aria-live="polite"
              >
                <div className="flex items-center justify-between text-sm font-semibold">
                  <span className="text-indigo-300 animate-pulse">
                    {generationStatus || "Ready"}
                  </span>
                  <span className="text-indigo-400 font-mono">
                    {generationProgress}%
                  </span>
                </div>

                <div className="h-2 overflow-hidden rounded-full bg-white/5">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-purple-500 transition-all duration-500 shadow-lg"
                    style={{
                      width: `${generationProgress}%`,
                    }}
                  />
                </div>
              </div>
            )}

            {generationError && (
              <div
                className="rounded-2xl border border-red-500/20 bg-red-950/20 p-4 text-sm font-medium text-red-400 flex items-center gap-2"
                role="alert"
              >
                <span>⚠️</span>
                <span>{generationError}</span>
              </div>
            )}
          </div>

          <div className="mt-8 space-y-3">
            <button
              disabled={!canGenerate}
              onClick={() => handleGenerate(false)}
              className="w-full bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold py-4 rounded-2xl shadow-lg shadow-indigo-600/10 hover:shadow-indigo-600/30 active:scale-[0.99] transition-all duration-200 disabled:opacity-30 disabled:from-gray-800 disabled:to-gray-800 disabled:text-gray-500 disabled:cursor-not-allowed disabled:shadow-none cursor-pointer"
            >
              {loading && activeMode === "normal" ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-white border-t-transparent" />
                  Processing Art...
                </span>
              ) : (
                "Generate AI Masterpiece"
              )}
            </button>

            <button
              disabled={!canGenerate}
              onClick={() => handleGenerate(true)}
              title="Keeps the style's background, outfit, and pose the same — only swaps in your face"
              className="w-full bg-white/5 hover:bg-white/10 border border-white/10 hover:border-indigo-500/40 text-white font-bold py-4 rounded-2xl transition-all duration-200 active:scale-[0.99] disabled:opacity-30 disabled:cursor-not-allowed cursor-pointer"
            >
              {loading && activeMode === "same-background" ? (
                <span className="flex items-center justify-center gap-2">
                  <span className="h-4 w-4 animate-spin rounded-full border-2 border-indigo-300 border-t-transparent" />
                  Keeping Background...
                </span>
              ) : (
                "Generate — Keep Same Background"
              )}
            </button>
            <p className="text-center text-xs text-gray-500">
              Same background, outfit &amp; pose as the sample — only your face changes.
            </p>
          </div>
        </div>
      </section>

      {/* Recent Generations Gallery */}
      <RecentGallery refreshTrigger={refreshTrigger} />

      {/* Result Lightbox Modal */}
      <ResultModal
        image={generatedImage}
        onClose={() => setGeneratedImage("")}
      />
    </div>
  );
}
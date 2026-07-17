"use client";

import { useEffect, useState } from "react";

import { getStyles, getImageUrl } from "@/lib/api";

import type {
  SelectedStyle,
  Style,
} from "@/types/style";

import StyleCard from "./StyleCard";

interface GalleryProps {
  search: string;
  category: string;

  selectedStyle: SelectedStyle | null;

  onSelect: (style: SelectedStyle) => void;
}

export default function Gallery({
  search,
  category,
  selectedStyle,
  onSelect,
}: GalleryProps) {
  const [styles, setStyles] = useState<Style[]>([]);
  const [activeFolder, setActiveFolder] = useState<Style | null>(null);

  const [loading, setLoading] = useState(true);

  const [error, setError] = useState("");

  useEffect(() => {
    setActiveFolder(null);
    loadStyles();
  }, [search, category]);

  async function loadStyles() {
    try {
      setLoading(true);

      const response = await getStyles({
        page: 1,
        limit: 100,
        search: search || undefined,
        category:
          category === "All"
            ? undefined
            : category.toLowerCase(),
      });

      setStyles(response.items);

      setError("");
    } catch (err) {
      console.error(err);

      setError("Unable to load styles.");
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div
        className="
          grid
          grid-cols-2
          gap-5
          md:grid-cols-3
          lg:grid-cols-4
          xl:grid-cols-5
        "
      >
        {Array.from({ length: 10 }).map((_, index) => (
          <div
            key={index}
            className="
              aspect-square
              animate-pulse
              rounded-2xl
              bg-white/5
            "
          />
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div
        className="
          rounded-2xl
          border
          border-red-500/20
          bg-red-950/20
          p-8
          text-center
          text-red-400
        "
      >
        {error}
      </div>
    );
  }

  if (styles.length === 0) {
    return (
      <div
        className="
          rounded-2xl
          border
          border-white/5
          bg-white/5
          p-10
          text-center
          text-gray-400
        "
      >
        No styles found.
      </div>
    );
  }

  if (activeFolder) {
    return (
      <div className="space-y-8 animate-fade-in">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between border-b border-white/5 pb-6">
          <div>
            <button
              onClick={() => setActiveFolder(null)}
              className="inline-flex items-center gap-2 rounded-xl bg-white/5 px-4 py-2 text-sm font-semibold text-gray-300 hover:bg-white/10 hover:text-white transition-all cursor-pointer border border-white/5"
            >
              ← Back to Styles
            </button>
            <h3 className="mt-4 text-2xl font-bold text-white font-outfit">
              {activeFolder.title}
            </h3>
            <p className="mt-1 text-sm text-gray-400">
              Select one of the {activeFolder.cards?.length} premium prompt cards inside this folder.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-5 md:grid-cols-3 lg:grid-cols-4 xl:grid-cols-5">
          {activeFolder.cards?.map((card, index) => {
              const cardId = card.prompt_id; // <-- use backend-generated ID

              const isSelected = selectedStyle?.id === cardId;

              return (
                <StyleCard
                  key={cardId}
                  id={cardId}
                  title={`Option ${index + 1}`}
                  category={activeFolder.category}
                  image={getImageUrl(card.image_url)}
                  selected={isSelected}
                  onClick={() =>
                    onSelect({
                      id: cardId,
                      title: `${activeFolder.title} (Option ${index + 1})`,
                      thumbnail: card.image_url,
                    })
                  }
                />
              );
            })}
        </div>
      </div>
    );
  }

  return (
    <div
      className="
        grid
        grid-cols-2
        gap-5
        md:grid-cols-3
        lg:grid-cols-4
        xl:grid-cols-5
      "
    >
      {styles.map((style) => (
        <StyleCard
          key={style.id}
          id={style.id}
          title={style.title}
          category={style.category}
          image={getImageUrl(style.thumbnail || style.image_url || "")}
          cardCount={style.card_count}
          selected={
            selectedStyle?.id === style.id ||
            (selectedStyle?.id ? selectedStyle.id.startsWith(style.id + "::p") : false)
          }
          onClick={() => {
            if (style.cards && style.cards.length > 0) {
              setActiveFolder(style);
            } else {
              onSelect({
                id: style.id,
                title: style.title,
                thumbnail: style.thumbnail || style.image_url || "",
              });
            }
          }}
        />
      ))}
    </div>
  );
}
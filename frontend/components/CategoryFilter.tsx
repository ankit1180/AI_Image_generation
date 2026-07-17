"use client";

import { useEffect, useState } from "react";

import { getCategories } from "@/lib/api";

interface CategoryFilterProps {
  selected: string;
  setSelected: (category: string) => void;
}

export default function CategoryFilter({
  selected,
  setSelected,
}: CategoryFilterProps) {
  const [categories, setCategories] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadCategories();
  }, []);

  async function loadCategories() {
    try {
      setLoading(true);

      const response = await getCategories();

      setCategories(["All", ...response.items]);
    } catch (error) {
      console.error(error);

      // Fallback
      setCategories(["All"]);
    } finally {
      setLoading(false);
    }
  }

  if (loading) {
    return (
      <div className="flex gap-3 overflow-x-auto pb-2">
        {Array.from({ length: 6 }).map((_, index) => (
          <div
            key={index}
            className="h-10 w-24 animate-pulse rounded-full bg-white/5"
          />
        ))}
      </div>
    );
  }

  return (
    <div
      className="
        flex
        gap-3
        overflow-x-auto
        pb-2
        scrollbar-hide
      "
    >
      {categories.map((category) => {
        const active = selected === category;

        return (
          <button
            key={category}
            type="button"
            onClick={() => setSelected(category)}
            className={`
              whitespace-nowrap
              rounded-full
              border
              px-5
              py-2
              text-xs
              font-bold
              tracking-wide
              transition-all
              duration-300
              cursor-pointer

              ${
                active
                  ? "border-indigo-500/30 bg-gradient-to-r from-indigo-600 to-purple-600 text-white shadow-lg shadow-indigo-600/20"
                  : "border-white/5 bg-white/5 text-gray-400 hover:border-white/10 hover:bg-white/10 hover:text-white"
              }
            `}
          >
            {category}
          </button>
        );
      })}
    </div>
  );
}
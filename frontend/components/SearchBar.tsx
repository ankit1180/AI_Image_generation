"use client";

import { Search, X } from "lucide-react";
import { useEffect, useState } from "react";

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
}

export default function SearchBar({
  value,
  onChange,
  placeholder = "Search styles...",
}: SearchBarProps) {
  const [inputValue, setInputValue] = useState(value);

  /**
   * Keep local state synchronized
   * when parent updates value.
   */
  useEffect(() => {
    setInputValue(value);
  }, [value]);

  /**
   * Debounce API calls
   */
  useEffect(() => {
    const timer = setTimeout(() => {
      onChange(inputValue.trim());
    }, 300);

    return () => clearTimeout(timer);
  }, [inputValue, onChange]);

  function clearSearch() {
    setInputValue("");
    onChange("");
  }

  return (
    <div className="relative w-full">
      {/* Search Icon */}
      <Search
        size={18}
        className="
          pointer-events-none
          absolute
          left-4
          top-1/2
          -translate-y-1/2
          text-gray-400
        "
      />

      {/* Input */}
      <input
        type="text"
        value={inputValue}
        placeholder={placeholder}
        autoComplete="off"
        spellCheck={false}
        onChange={(event) =>
          setInputValue(event.target.value)
        }
        className="
          h-12
          w-full
          rounded-2xl
          border
          border-white/10
          bg-white/5
          pl-12
          pr-12
          text-sm
          text-white
          outline-none
          transition-all
          duration-300
          placeholder:text-gray-500
          focus:border-indigo-500/40
          focus:bg-white/10
          focus:ring-2
          focus:ring-indigo-500/15
        "
      />

      {/* Clear Button */}
      {inputValue.length > 0 && (
        <button
          type="button"
          onClick={clearSearch}
          aria-label="Clear search"
          className="
            absolute
            right-3
            top-1/2
            flex
            h-8
            w-8
            -translate-y-1/2
            items-center
            justify-center
            rounded-full
            text-gray-400
            transition-colors
            hover:bg-white/10
            hover:text-white
          "
        >
          <X
            size={16}
          />
        </button>
      )}
    </div>
  );
}
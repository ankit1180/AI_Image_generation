"use client";

import { Check } from "lucide-react";
import { motion } from "framer-motion";

interface StyleCardProps {
  id: string;
  title: string;
  category: string;
  image: string;
  selected: boolean;
  onClick: () => void;
  cardCount?: number;
}

export default function StyleCard({
  title,
  category,
  image,
  selected,
  onClick,
  cardCount,
}: StyleCardProps) {
  return (
    <motion.button
      whileHover={{
        y: -4,
        scale: 1.02,
      }}
      whileTap={{
        scale: 0.98,
      }}
      onClick={onClick}
      className={`
        group
        relative
        overflow-hidden
        rounded-2xl
        border
        bg-white/5
        shadow-lg
        transition-all
        duration-300
        cursor-pointer
        ${
          selected
            ? "border-indigo-500 ring-2 ring-indigo-500/30"
            : "border-white/5 hover:border-white/20 hover:shadow-neon"
        }
      `}
    >
      {/* Image */}
      <div className="aspect-square overflow-hidden bg-white/5">
        <img
          src={image}
          alt={title}
          draggable={false}
          loading="lazy"
          className="
            h-full
            w-full
            object-cover
            transition-transform
            duration-700
            ease-out
            group-hover:scale-105
          "
        />
      </div>

      {/* Category Badge */}
      <div className="absolute left-3 top-3">
        <span
          className="
            rounded-full
            bg-black/60
            border
            border-white/10
            px-2.5
            py-1
            text-[10px]
            font-bold
            uppercase
            tracking-wider
            text-gray-300
            backdrop-blur-md
          "
        >
          {category}
        </span>
      </div>

      {/* Folder Badge */}
      {cardCount !== undefined && cardCount > 0 && (
        <div className="absolute left-3 top-10">
          <span
            className="
              rounded-full
              bg-indigo-600/80
              border
              border-indigo-400/30
              px-2.5
              py-1
              text-[10px]
              font-bold
              uppercase
              tracking-wider
              text-white
              backdrop-blur-md
              shadow-lg
              shadow-indigo-600/20
            "
          >
            📁 Folder • {cardCount}
          </span>
        </div>
      )}

      {/* Selected Icon */}
      {selected && (
        <div
          className="
            absolute
            right-3
            top-3
            flex
            h-7
            w-7
            items-center
            justify-center
            rounded-full
            bg-indigo-600
            text-white
            shadow-md
            shadow-indigo-600/30
            animate-scale-in
          "
        >
          <Check size={14} strokeWidth={3} />
        </div>
      )}

      {/* Bottom Overlay */}
      <div
        className="
          absolute
          inset-x-0
          bottom-0
          bg-gradient-to-t
          from-black/90
          via-black/40
          to-transparent
          p-4
          text-left
          pt-12
        "
      >
        <h3
          className="
            line-clamp-1
            text-sm
            font-bold
            text-white
            font-outfit
          "
        >
          {title}
        </h3>
      </div>
    </motion.button>
  );
}
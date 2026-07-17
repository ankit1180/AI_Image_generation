"use client";

import { Download, X } from "lucide-react";

import { getImageUrl } from "@/lib/api";

interface ResultModalProps {
  image: string;
  onClose: () => void;
}

export default function ResultModal({
  image,
  onClose,
}: ResultModalProps) {
  if (!image) {
    return null;
  }

  const imageUrl = getImageUrl(image);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/85 backdrop-blur-sm p-4">
      <div className="w-full max-w-2xl overflow-hidden rounded-3xl border border-white/10 bg-[#0b0b18] shadow-2xl animate-scale-in">
        <div className="flex items-center justify-between border-b border-white/5 px-6 py-4 bg-[#090914]">
          <h2 className="text-sm font-bold text-white uppercase tracking-wider font-outfit">
            Generated Masterpiece
          </h2>

          <button
            type="button"
            aria-label="Close result"
            onClick={onClose}
            className="flex h-8 w-8 items-center justify-center rounded-full bg-white/5 border border-white/10 text-gray-400 hover:bg-white/10 hover:text-white transition cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>

        <div className="bg-black/35 p-6 flex justify-center items-center">
          <img
            src={imageUrl}
            alt="Generated result"
            className="mx-auto max-h-[60vh] rounded-2xl object-contain border border-white/10 shadow-2xl"
          />
        </div>

        <div className="flex justify-end gap-3 border-t border-white/5 bg-[#090914] px-6 py-4">
          <a
            href={imageUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-2 rounded-xl bg-gradient-to-r from-indigo-600 to-purple-600 px-5 py-3 text-xs font-bold text-white hover:from-indigo-500 hover:to-purple-500 active:scale-95 transition cursor-pointer shadow-lg shadow-indigo-600/10"
          >
            <Download size={14} strokeWidth={2.5} />
            Download Artwork
          </a>
        </div>
      </div>
    </div>
  );
}

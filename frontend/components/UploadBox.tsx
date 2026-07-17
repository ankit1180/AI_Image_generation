"use client";

import { ImagePlus, X } from "lucide-react";
import { useEffect, useMemo } from "react";
import { useDropzone } from "react-dropzone";

interface UploadBoxProps {
  file: File | null;
  onChange: (file: File | null) => void;
}

export default function UploadBox({
  file,
  onChange,
}: UploadBoxProps) {
  const previewUrl = useMemo(() => {
    if (!file) {
      return "";
    }

    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const { getRootProps, getInputProps, isDragActive } =
    useDropzone({
      accept: {
        "image/jpeg": [".jpg", ".jpeg"],
        "image/png": [".png"],
        "image/webp": [".webp"],
      },
      maxFiles: 1,
      maxSize: 10 * 1024 * 1024,
      multiple: false,
      onDrop: (acceptedFiles) => {
        onChange(acceptedFiles[0] ?? null);
      },
    });

  if (file) {
    return (
      <div className="space-y-4">
        <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-white/5 p-2 group shadow-2xl">
          <img
            src={previewUrl}
            alt={file.name}
            className="aspect-video w-full object-contain rounded-xl bg-black/40"
          />

          <button
            type="button"
            aria-label="Remove uploaded image"
            onClick={() => onChange(null)}
            className="absolute right-5 top-5 flex h-8 w-8 items-center justify-center rounded-full bg-black/60 border border-white/10 text-gray-300 shadow-lg hover:bg-black/85 hover:text-white backdrop-blur transition-all duration-200 cursor-pointer"
          >
            <X size={14} />
          </button>
        </div>

        <div className="flex items-center justify-between gap-4 text-xs font-bold text-gray-400 px-1">
          <span className="truncate">{file.name}</span>
          <span className="font-mono text-gray-500">{Math.ceil(file.size / 1024)} KB</span>
        </div>
      </div>
    );
  }

  return (
    <div
      {...getRootProps()}
      className={`
        flex
        min-h-[256px]
        items-center
        justify-center
        p-8
        text-center
        rounded-2xl
        border-2
        border-dashed
        transition-all
        duration-300
        cursor-pointer
        ${
          isDragActive
            ? "border-indigo-500 bg-indigo-500/5 shadow-inner"
            : "border-white/10 bg-white/5 hover:border-indigo-500/40 hover:bg-white/10"
        }
      `}
    >
      <input {...getInputProps()} />

      <div className="space-y-4">
        <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-indigo-500/10 text-indigo-400 group-hover:scale-110 transition duration-300">
          <ImagePlus size={22} />
        </div>

        <div>
          <p className="font-bold text-white font-outfit text-base">
            Drop your image here
          </p>
          <p className="mt-1 text-sm text-gray-400 font-light">
            or click to browse from device
          </p>
        </div>
      </div>
    </div>
  );
}

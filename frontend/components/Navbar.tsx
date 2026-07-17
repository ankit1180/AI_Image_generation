"use client";

import { Sparkles } from "lucide-react";
import { motion } from "framer-motion";

export default function Navbar() {
  return (
    <motion.header
      initial={{
        opacity: 0,
        y: -20,
      }}
      animate={{
        opacity: 1,
        y: 0,
      }}
      className="
        sticky
        top-0
        z-50
        border-b
        border-white/5
        bg-[#05050a]/75
        backdrop-blur-xl
      "
    >
      <div className="mx-auto flex h-20 max-w-7xl items-center justify-between px-4 sm:px-6 lg:px-8">
        <div className="flex items-center gap-3">
          <div
            className="
              flex
              h-11
              w-11
              items-center
              justify-center
              rounded-2xl
              bg-gradient-to-br
              from-indigo-500
              to-purple-600
              text-white
              shadow-lg
              shadow-indigo-500/20
            "
          >
            <Sparkles size={20} />
          </div>

          <div>
            <h1 className="text-lg font-bold text-white font-outfit tracking-tight">
              AI Style Studio
            </h1>

            <p className="text-[10px] uppercase font-bold tracking-widest text-indigo-400">
              Creative Lab
            </p>
          </div>
        </div>

        <nav className="hidden gap-8 md:flex">
          <a
            href="#styles"
            className="text-sm font-medium text-gray-400 transition hover:text-white"
          >
            Styles
          </a>

          <a
            href="#generate"
            className="text-sm font-medium text-gray-400 transition hover:text-white"
          >
            Studio
          </a>

          <a
            href="#gallery"
            className="text-sm font-medium text-gray-400 transition hover:text-white"
          >
            Recent Work
          </a>
        </nav>

        <div>
          <a
            href="#generate"
            className="
              inline-block
              rounded-xl
              bg-gradient-to-r
              from-indigo-600
              to-purple-600
              px-5
              py-2.5
              text-xs
              font-bold
              text-white
              transition
              hover:from-indigo-500
              hover:to-purple-500
              hover:shadow-lg
              hover:shadow-indigo-500/20
              active:scale-95
              cursor-pointer
            "
          >
            Get Started
          </a>
        </div>
      </div>
    </motion.header>
  );
}
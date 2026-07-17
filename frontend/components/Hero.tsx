"use client";

import { Upload, Wand2 } from "lucide-react";
import { motion } from "framer-motion";

export default function Hero() {
  return (
    <section className="relative overflow-hidden py-16 md:py-24">
      {/* Background glow blobs */}
      <div
        className="
          absolute
          left-1/4
          -top-20
          h-[350px]
          w-[350px]
          rounded-full
          bg-gradient-to-r
          from-indigo-500/15
          to-purple-500/15
          opacity-50
          blur-[100px]
          pointer-events-none
        "
      />
      <div
        className="
          absolute
          right-1/4
          top-10
          h-[300px]
          w-[300px]
          rounded-full
          bg-gradient-to-r
          from-purple-500/10
          to-pink-500/10
          opacity-40
          blur-[100px]
          pointer-events-none
        "
      />

      <div className="relative mx-auto max-w-4xl text-center z-10 px-4">
        <motion.div
          initial={{
            opacity: 0,
            y: 10,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          className="
            inline-flex
            items-center
            gap-2
            rounded-full
            border
            border-indigo-500/25
            bg-indigo-950/20
            px-4
            py-1.5
            text-xs
            font-semibold
            tracking-wide
            text-indigo-300
            backdrop-blur-md
          "
        >
          <span className="flex h-1.5 w-1.5 rounded-full bg-indigo-400" />
          ✨ Next-Gen AI Art Engine
        </motion.div>

        <motion.h1
          initial={{
            opacity: 0,
            y: 20,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            delay: 0.1,
          }}
          className="
            mt-6
            text-4xl
            sm:text-5xl
            md:text-6xl
            font-black
            tracking-tight
            text-white
            font-outfit
            leading-[1.1]
          "
        >
          Transform Photos into
          <br />
          <span className="gradient-text">Stunning AI Art</span>
        </motion.h1>

        <motion.p
          initial={{
            opacity: 0,
            y: 15,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            delay: 0.2,
          }}
          className="
            mx-auto
            mt-6
            max-w-2xl
            text-base
            sm:text-lg
            md:text-xl
            text-gray-400
            font-light
            leading-relaxed
          "
        >
          Upload any image, choose from curated AI styles, and generate beautiful artwork in seconds.
        </motion.p>

        <motion.div
          initial={{
            opacity: 0,
            y: 20,
          }}
          animate={{
            opacity: 1,
            y: 0,
          }}
          transition={{
            delay: 0.3,
          }}
          className="
            mt-10
            flex
            flex-col
            sm:flex-row
            justify-center
            items-center
            gap-4
          "
        >
          <a
            href="#generate"
            className="
              w-full
              sm:w-auto
              flex
              items-center
              justify-center
              gap-2
              rounded-2xl
              bg-gradient-to-r
              from-indigo-600
              to-purple-600
              px-8
              py-4
              font-bold
              text-white
              shadow-lg
              shadow-indigo-500/10
              transition
              hover:from-indigo-500
              hover:to-purple-500
              hover:shadow-indigo-500/25
              hover:scale-[1.02]
              active:scale-[0.98]
              cursor-pointer
            "
          >
            <Upload size={18} />
            Start Creating
          </a>

          <a
            href="#styles"
            className="
              w-full
              sm:w-auto
              flex
              items-center
              justify-center
              gap-2
              rounded-2xl
              border
              border-white/10
              bg-white/5
              px-8
              py-4
              font-bold
              text-gray-300
              transition
              hover:bg-white/10
              hover:text-white
              hover:scale-[1.02]
              active:scale-[0.98]
              cursor-pointer
            "
          >
            <Wand2 size={18} />
            Explore Styles
          </a>
        </motion.div>
      </div>
    </section>
  );
}
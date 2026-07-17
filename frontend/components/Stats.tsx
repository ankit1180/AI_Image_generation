"use client";

import { motion } from "framer-motion";

const stats = [
  {
    number: "25+",
    label: "AI Styles Ready",
  },
  {
    number: "10K+",
    label: "Artwork Generated",
  },
  {
    number: "99%",
    label: "Customer Rating",
  },
];

export default function Stats() {
  return (
    <section className="py-6">
      <div className="mx-auto grid max-w-5xl grid-cols-1 md:grid-cols-3 gap-6">
        {stats.map((item, index) => (
          <motion.div
            key={item.label}
            initial={{
              opacity: 0,
              y: 20,
            }}
            animate={{
              opacity: 1,
              y: 0,
            }}
            transition={{
              delay: index * 0.1,
            }}
            className="
              glass-card
              rounded-3xl
              p-6
              md:p-8
              text-center
              shadow-lg
              relative
              overflow-hidden
            "
          >
            <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-indigo-500/0 via-indigo-500/20 to-purple-500/0" />
            <h2 className="text-4xl md:text-5xl font-black font-outfit text-transparent bg-clip-text bg-gradient-to-r from-indigo-300 via-indigo-400 to-purple-400">
              {item.number}
            </h2>

            <p className="mt-2 text-xs md:text-sm font-semibold tracking-wider uppercase text-gray-400">
              {item.label}
            </p>
          </motion.div>
        ))}
      </div>
    </section>
  );
}
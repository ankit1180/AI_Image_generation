import type { Metadata } from "next";
import { Inter, Outfit } from "next/font/google";
import Navbar from "@/components/Navbar";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

export const metadata: Metadata = {
  title: "AI Style Studio | Premium Image Transformations",
  description:
    "Upload any image, choose from dozens of curated AI styles, and generate beautiful artwork in seconds with our state-of-the-art AI transformation studio.",
};

interface RootLayoutProps {
  children: React.ReactNode;
}

export default function RootLayout({
  children,
}: Readonly<RootLayoutProps>) {
  return (
    <html lang="en" className={`scroll-smooth dark ${inter.variable} ${outfit.variable}`}>
      <body className="bg-[#05050a] text-gray-200 min-h-screen flex flex-col antialiased selection:bg-indigo-600 selection:text-white relative overflow-x-hidden">
        {/* Subtle mesh background grid */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#1f293710_1px,transparent_1px),linear-gradient(to_bottom,#1f293710_1px,transparent_1px)] bg-[size:4rem_4rem] [mask-image:radial-gradient(ellipse_60%_50%_at_50%_0%,#000_70%,transparent_100%)] pointer-events-none z-0" />
        
        {/* Header / Navigation */}
        <Navbar />

        {/* Main Content */}
        <main className="flex-grow z-10 relative">
          <div className="mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
            {children}
          </div>
        </main>

        {/* Footer */}
        <footer className="border-t border-white/5 bg-[#030308] z-10 relative">
          <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs sm:text-sm text-gray-500">
            <div>
              <span className="font-bold text-gray-400">AI Style Studio</span> © {new Date().getFullYear()}.
            </div>
            <div className="flex gap-6">
              <a href="#styles" className="hover:text-gray-300 transition">Styles</a>
              <a href="#generate" className="hover:text-gray-300 transition">Studio</a>
              <a href="#gallery" className="hover:text-gray-300 transition">Gallery</a>
            </div>
          </div>
        </footer>
      </body>
    </html>
  );
}


import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "Freeside | Energy-Aware Productivity",
  description: "AI co-pilot that routes tasks based on your actual mental capacity.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${inter.variable} h-full antialiased font-sans`}
    >
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}

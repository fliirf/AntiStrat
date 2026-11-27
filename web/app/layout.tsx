import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "AntiStrat",
  description: "VALORANT Tactical Manager: opponent prep for coaches",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}

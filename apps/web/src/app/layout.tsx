import type { Metadata } from "next";
import "./globals.css";
import { PWARegister } from "@/components/pwa-register";

export const metadata: Metadata = {
  title: "Lecturer Support Agent",
  description: "AI-native teaching and learning support for higher education.",
  manifest: "/manifest.webmanifest",
  applicationName: "Lecturer Support Agent",
  appleWebApp: { capable: true, title: "Lecturer AI", statusBarStyle: "default" },
  icons: { icon: "/icon.svg", apple: "/icon.svg" },
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body><PWARegister />{children}</body>
    </html>
  );
}

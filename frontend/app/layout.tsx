import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "GovIntel AI",
  description: "Inteligência documental para editais públicos.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="pt-BR">
      <body>{children}</body>
    </html>
  );
}

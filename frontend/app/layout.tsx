import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "SRCC FAQ Bot",
  description: "囲碁ロボット(SRCC) コールセンター用 FAQ・用語集ボット",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="ja">
      <body className="bg-gray-50 text-gray-900 overflow-hidden">{children}</body>
    </html>
  );
}

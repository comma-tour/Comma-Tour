import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "쉼표투어 | 여유를 찾는 여행",
  description: "붐비는 관광지 대신 나와 맞는 한적한 명소와 여행 코스를 만나보세요.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body>{children}</body>
    </html>
  );
}

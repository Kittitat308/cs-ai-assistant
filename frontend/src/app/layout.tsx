import type { Metadata } from "next";

import "./globals.css";


export const metadata: Metadata = {
  title: "CS AI Assistant",
  description:
    "AI Assistant for Computer Science Department",
};


export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="th">
      <body>
        {children}
      </body>
    </html>
  );
}
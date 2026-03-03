import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Intelli-Credit — AI-Powered Credit Appraisal",
  description: "Enterprise AI credit appraisal platform for smarter lending decisions",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body>{children}</body>
    </html>
  );
}

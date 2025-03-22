import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { SocketProvider } from './socket-provider'

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

export const metadata: Metadata = {
  title: "XplainCrypto - Cryptocurrency Research Reports",
  description: "Generate comprehensive, research-backed reports on any cryptocurrency",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.variable} antialiased`}>
        <SocketProvider>
          {children}
        </SocketProvider>
      </body>
    </html>
  );
}
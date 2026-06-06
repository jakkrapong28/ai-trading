import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import "./globals.css";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Team AI Trading Office - ห้องบัญชาการและระเบียบภาษี",
  description: "ระบบบูรณาการเทรดอัตโนมัติด้วย AI Agents, สมุดบัญชี Ledger ERP และ Team Tax Compliance สะสม",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="th"
      className={`${manrope.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col font-sans">{children}</body>
    </html>
  );
}

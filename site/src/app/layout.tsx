import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "IrishHealthData.com",
  description:
    "An open, evidence-based, reproducible digital observatory of the Irish healthcare system.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" className="h-full antialiased" suppressHydrationWarning>
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}

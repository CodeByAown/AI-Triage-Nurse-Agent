import type { Metadata, Viewport } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { ThemeProvider } from "next-themes";
import { Toaster } from "sonner";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

export const metadata: Metadata = {
  title: {
    default: "Neural Hub — AI Triage Nurse",
    template: "%s | Neural Hub",
  },
  description:
    "AI-powered patient triage and clinical decision support. Assess urgency, identify risk, and route patients to the right care.",
  keywords: ["healthcare AI", "triage", "patient intake", "clinical decision support", "AI nurse"],
  authors: [{ name: "Neural Hub" }],
  creator: "Neural Hub",
  robots: {
    index: false, // Healthcare app — private
    follow: false,
  },
  icons: {
    icon: "/favicon.ico",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fcfbf7" },
    { media: "(prefers-color-scheme: dark)", color: "#101a15" },
  ],
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={`${inter.variable} ${jetbrainsMono.variable} font-sans`} suppressHydrationWarning>
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          forcedTheme="light"
          enableSystem={false}
          disableTransitionOnChange
        >
          {children}
          <Toaster
            position="top-right"
            richColors
            expand
            toastOptions={{
              style: { fontFamily: "var(--font-inter)" },
            }}
          />
        </ThemeProvider>
      </body>
    </html>
  );
}

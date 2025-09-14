import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Header from "@/components/Header";
import { RegistrationStatus } from "@/components/RegistrationStatus";
import AuthGuard from "@/components/AuthGuard";
import "./globals.css";
import { Providers } from "./providers";

const geistSans = Geist({
    variable: "--font-geist-sans",
    subsets: ["latin"],
});

const geistMono = Geist_Mono({
    variable: "--font-geist-mono",
    subsets: ["latin"],
});

// Build absolute metadata URLs using the public site URL when available.
const siteUrl = process.env.NEXT_PUBLIC_SITE_URL?.trim() || "http://localhost:3000";

export const metadata: Metadata = {
    metadataBase: new URL(siteUrl),
    title: {
        default: "SafeLens: Harmful Video Moderation",
        template: "%s | SafeLens",
    },
    description:
        "AI-powered video content moderation platform for detecting harmful content",
    keywords: [
        "content moderation",
        "video analysis",
        "harmful content detection",
        "AI moderation",
    ],
    authors: [{ name: "SocialAI Studio" }],
    alternates: {
        canonical: "/",
    },
    robots: {
        index: true,
        follow: true,
    },
    openGraph: {
        title: "SafeLens: Harmful Video Moderation",
        description:
            "AI-powered video content moderation platform for detecting harmful content",
        siteName: "SafeLens",
        url: "/",
        images: [
            {
                url: "/SafeLens.png",
                alt: "SafeLens: Harmful Video Moderation",
            },
        ],
        locale: "en_US",
        type: "website",
    },
    twitter: {
        card: "summary_large_image",
        title: "SafeLens: Harmful Video Moderation",
        description:
            "AI-powered video content moderation platform for detecting harmful content",
        images: ["/SafeLens.png"],
    },
};

export default function RootLayout({
    children,
}: Readonly<{
    children: React.ReactNode;
}>) {
    return (
        <html lang="en">
            <body className={`${geistSans.variable} ${geistMono.variable} antialiased`}>
                <Providers>
                    <AuthGuard>
                        <div className="min-h-screen bg-background">
                            <Header />
                            {children}
                            <RegistrationStatus />
                        </div>
                    </AuthGuard>
                </Providers>
            </body>
        </html>
    );
}

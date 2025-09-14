"use client";

import { useEffect, useState } from "react";
import Image from "next/image";
import { Button } from "@/components/ui/button";

export default function HowItWorksButton() {
    const [open, setOpen] = useState(false);

    // Close on ESC for accessibility
    useEffect(() => {
        if (!open) return;
        const onKey = (e: KeyboardEvent) => {
            if (e.key === "Escape") setOpen(false);
        };
        window.addEventListener("keydown", onKey);
        return () => window.removeEventListener("keydown", onKey);
    }, [open]);

    // Allow other parts of the app (e.g., avatar menu) to open this modal
    useEffect(() => {
        const onOpen = () => setOpen(true);
        window.addEventListener("open-how-it-works", onOpen as EventListener);
        return () =>
            window.removeEventListener("open-how-it-works", onOpen as EventListener);
    }, []);

    return (
        <>
            {/* Visible text button on md+, compact icon on small screens */}
            <Button
                variant="outline"
                onClick={() => setOpen(true)}
                aria-haspopup="dialog"
                className="hidden md:inline-flex"
            >
                How it works
            </Button>
            <Button
                variant="ghost"
                size="icon"
                onClick={() => setOpen(true)}
                aria-label="How it works"
                className="md:hidden"
            >
                ?
            </Button>

            {open && (
                <div
                    className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm"
                    onClick={() => setOpen(false)}
                    aria-hidden={!open}
                >
                    <div
                        role="dialog"
                        aria-modal="true"
                        aria-label="How the app works"
                        className="relative w-[min(92vw,1100px)] max-h-[88vh] rounded-xl border border-border bg-background shadow-2xl"
                        onClick={(e) => e.stopPropagation()}
                    >
                        <div className="flex items-center justify-between px-4 py-3 border-b border-border">
                            <h2 className="text-base font-semibold">
                                SafeLens: Hateful Video Moderation – Overview
                            </h2>
                            <Button
                                variant="ghost"
                                size="icon"
                                aria-label="Close"
                                onClick={() => setOpen(false)}
                            >
                                {/* simple × icon without extra deps */}
                                <span className="text-xl leading-none">×</span>
                            </Button>
                        </div>

                        <div className="p-4">
                            {/* Place the diagram at frontend/public/flow-diagram.png */}
                            <div className="w-full overflow-auto">
                                <Image
                                    src="/Flow Diagram.jpg"
                                    alt="High-level pipeline: upload/link → transcribe → flag → analyze → result"
                                    width={1800}
                                    height={820}
                                    className="w-full h-auto max-h-[72vh] object-contain"
                                    priority={false}
                                />
                            </div>
                            <p className="mt-3 text-sm text-muted-foreground">
                                Tip: This is a high-level view. Detailed behavior and
                                edge cases live in the project guide.
                            </p>
                        </div>
                    </div>
                </div>
            )}
        </>
    );
}

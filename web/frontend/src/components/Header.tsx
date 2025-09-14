"use client";

import Image from "next/image";
import { useRouter } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Skeleton } from "@/components/ui/skeleton";
import HowItWorksButton from "@/components/HowItWorksButton";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export default function Header() {
    const router = useRouter();
    const { data: session, status } = useSession();
    const user = session?.user;

    const handleLogout = () => {
        signOut();
    };

    const getInitials = (name: string) => {
        return name
            .split(" ")
            .map((part) => part[0])
            .join("")
            .toUpperCase();
    };

    return (
        <header className="border-b border-border">
            <div className="container mx-auto px-4 py-4 flex items-center justify-between">
                <div
                    className="flex items-center gap-2 cursor-pointer hover:opacity-80 transition-opacity"
                    onClick={() => router.push("/")}
                >
                    <Image
                        src="/SafeLens.svg"
                        alt="SafeLens Logo"
                        width={32}
                        height={32}
                        className="object-contain"
                    />
                    <h1 className="text-xl font-semibold">
                        SafeLens: Hateful Video Moderation
                    </h1>
                </div>

                <div className="flex items-center gap-4">
                    {/* Non-intrusive helper to show the architecture diagram */}
                    <HowItWorksButton />
                    <DropdownMenu>
                        <DropdownMenuTrigger asChild>
                            <Avatar className="cursor-pointer">
                                {status === "loading" || !user ? (
                                    <Skeleton className="w-8 h-8 rounded-full" />
                                ) : user.image ? (
                                    <Image
                                        src={user.image}
                                        alt="User profile"
                                        width={32}
                                        height={32}
                                        className="rounded-full object-cover"
                                    />
                                ) : (
                                    <AvatarFallback>
                                        {getInitials(user?.name || "") ||
                                            user?.email?.[0] ||
                                            "U"}
                                    </AvatarFallback>
                                )}
                            </Avatar>
                        </DropdownMenuTrigger>
                        <DropdownMenuContent align="end">
                            <DropdownMenuItem onClick={handleLogout}>
                                Logout
                            </DropdownMenuItem>
                        </DropdownMenuContent>
                    </DropdownMenu>
                </div>
            </div>
        </header>
    );
}

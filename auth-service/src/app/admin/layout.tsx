import Link from "next/link";
import { AppWindow, Plus } from "lucide-react";
import UserInfo from "@/components/admin/user-info";
import { auth } from "@/lib/auth";
import { db } from "@/db";
import { users } from "@/db/schema";
import { eq } from "drizzle-orm";
import { redirect } from "next/navigation";
import { headers } from "next/headers";

export default async function AdminLayout({ children }: { children: React.ReactNode }) {
    // Server-side authentication check
    const session = await auth.api.getSession({
        headers: await headers(),
    });

    if (!session) {
        redirect("/sign-in?next=/admin");
    }

    // Get user role from session or database
    let role: string | null = (session.user as any)?.role ?? null;

    if (!role) {
        try {
            const row = await db
                .select({ role: users.role })
                .from(users)
                .where(eq(users.id, session.user.id))
                .limit(1);
            role = row?.[0]?.role ?? null;
        } catch (error) {
            redirect("/sign-in?next=/admin");
        }
    }

    if (role !== "ADMIN") {
        redirect("/sign-in?next=/admin");
    }
    return (
        <div className="min-h-screen flex">
            <aside className="hidden md:flex w-64 flex-col border-r bg-sidebar text-sidebar-foreground">
                <div className="h-16 px-4 flex items-center text-lg font-semibold">
                    SocialAI Admin
                </div>
                <nav className="px-2 py-2 space-y-1">
                    <Link
                        href="/admin/apps"
                        className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                    >
                        <AppWindow className="size-4" />
                        <span>Applications</span>
                    </Link>
                    <Link
                        href="/admin/apps/new"
                        className="flex items-center gap-2 rounded-md px-3 py-2 text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground"
                    >
                        <Plus className="size-4" />
                        <span>New Application</span>
                    </Link>
                </nav>
            </aside>
            <div className="flex-1 flex min-w-0 flex-col">
                <header className="h-16 border-b bg-background/70 backdrop-blur supports-[backdrop-filter]:bg-background/60">
                    <div className="h-full px-4 md:px-6 flex items-center justify-between">
                        <div className="flex items-center gap-3">
                            <span className="md:hidden font-semibold">Admin</span>
                        </div>
                        <UserInfo />
                    </div>
                </header>
                <main className="p-4 md:p-6">{children}</main>
            </div>
        </div>
    );
}

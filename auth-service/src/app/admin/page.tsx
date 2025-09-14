import Link from "next/link";
import { db } from "@/db";
import { users, oauthApplications, oauthAccessTokens } from "@/db/schema";
import { count, desc } from "drizzle-orm";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Users, AppWindow, KeyRound, Plus } from "lucide-react";

export default async function AdminDashboardPage() {
    const [{ value: usersCount }] = await db.select({ value: count() }).from(users);
    const [{ value: appsCount }] = await db
        .select({ value: count() })
        .from(oauthApplications);
    const [{ value: tokensCount }] = await db
        .select({ value: count() })
        .from(oauthAccessTokens);

    const recentApps = await db
        .select()
        .from(oauthApplications)
        .orderBy(desc(oauthApplications.createdAt))
        .limit(5);

    return (
        <div className="px-4 md:px-6">
            <div className="max-w-6xl mx-auto space-y-6">
                <div className="flex items-center justify-between">
                    <h1 className="text-xl md:text-2xl font-semibold">
                        Admin Dashboard
                    </h1>
                    <Button asChild>
                        <Link href="/admin/apps/new">
                            <Plus className="size-4" /> New Application
                        </Link>
                    </Button>
                </div>

                <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                Users
                            </CardTitle>
                            <Users className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-semibold">{usersCount}</div>
                            <p className="text-xs text-muted-foreground">
                                Registered accounts
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                Applications
                            </CardTitle>
                            <AppWindow className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-semibold">{appsCount}</div>
                            <p className="text-xs text-muted-foreground">
                                OIDC client registrations
                            </p>
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                            <CardTitle className="text-sm font-medium text-muted-foreground">
                                Tokens
                            </CardTitle>
                            <KeyRound className="size-4 text-muted-foreground" />
                        </CardHeader>
                        <CardContent>
                            <div className="text-2xl font-semibold">{tokensCount}</div>
                            <p className="text-xs text-muted-foreground">
                                Issued access tokens
                            </p>
                        </CardContent>
                    </Card>
                </div>

                <Card>
                    <CardHeader className="border-b">
                        <CardTitle>Recent Applications</CardTitle>
                    </CardHeader>
                    <CardContent>
                        {recentApps.length === 0 ? (
                            <div className="p-6 text-sm text-muted-foreground">
                                No applications yet. Create your first one.
                            </div>
                        ) : (
                            <div className="overflow-x-auto">
                                <table className="min-w-full text-sm">
                                    <thead className="bg-muted/50">
                                        <tr className="border-b">
                                            <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                                                Name
                                            </th>
                                            <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                                                Client ID
                                            </th>
                                            <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                                                Created
                                            </th>
                                        </tr>
                                    </thead>
                                    <tbody>
                                        {recentApps.map((a) => (
                                            <tr
                                                key={a.id}
                                                className="border-b last:border-0 hover:bg-muted/30"
                                            >
                                                <td className="px-4 py-3">{a.name}</td>
                                                <td className="px-4 py-3 font-mono text-xs break-all">
                                                    {a.clientId}
                                                </td>
                                                <td className="px-4 py-3">
                                                    {a.createdAt?.toLocaleString?.() ??
                                                        ""}
                                                </td>
                                            </tr>
                                        ))}
                                    </tbody>
                                </table>
                            </div>
                        )}
                        <div className="mt-4 flex gap-2">
                            <Button variant="outline" asChild>
                                <Link href="/admin/apps">View all</Link>
                            </Button>
                            <Button asChild>
                                <Link href="/admin/apps/new">
                                    <Plus className="size-4" /> New Application
                                </Link>
                            </Button>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </div>
    );
}

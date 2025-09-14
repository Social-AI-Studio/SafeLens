import Link from "next/link";
import { db } from "@/db";
import { oauthApplications } from "@/db/schema";
import { Button } from "@/components/ui/button";
import {
    Card,
    CardContent,
    CardHeader,
    CardTitle,
    CardAction,
} from "@/components/ui/card";
import { Plus } from "lucide-react";

export default async function AdminAppsPage() {
    const apps = await db
        .select()
        .from(oauthApplications)
        .orderBy(oauthApplications.createdAt);

    return (
        <div className="px-4 md:px-6">
            <Card className="max-w-6xl mx-auto">
                <CardHeader className="border-b">
                    <CardTitle className="text-xl md:text-2xl">
                        OIDC Applications
                    </CardTitle>
                    <CardAction>
                        <Button asChild>
                            <Link href="/admin/apps/new">
                                <Plus className="size-4" /> New Application
                            </Link>
                        </Button>
                    </CardAction>
                </CardHeader>
                <CardContent>
                    {apps.length === 0 ? (
                        <div className="p-6 text-sm text-muted-foreground">
                            No applications registered yet.
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
                                            Redirect URIs
                                        </th>
                                        <th className="text-left px-4 py-3 font-medium text-muted-foreground">
                                            Created
                                        </th>
                                    </tr>
                                </thead>
                                <tbody>
                                    {apps.map((a) => (
                                        <tr
                                            key={a.id}
                                            className="border-b last:border-0 hover:bg-muted/30"
                                        >
                                            <td className="px-4 py-3">{a.name}</td>
                                            <td className="px-4 py-3 font-mono text-xs break-all">
                                                {a.clientId}
                                            </td>
                                            <td className="px-4 py-3 text-xs break-all">
                                                {a.redirectURLs}
                                            </td>
                                            <td className="px-4 py-3">
                                                {a.createdAt?.toLocaleString?.() ?? ""}
                                            </td>
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}

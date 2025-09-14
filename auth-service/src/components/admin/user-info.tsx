"use client";

import { authClient } from "@/lib/auth-client";

export default function UserInfo() {
  const { data: session } = authClient.useSession();
  
  const display = session?.user?.name || session?.user?.email || "Admin";

  return (
    <div className="flex items-center gap-2 text-sm text-muted-foreground">
      <span className="hidden sm:inline">Signed in as</span>
      <span className="font-medium text-foreground">{display}</span>
    </div>
  );
}

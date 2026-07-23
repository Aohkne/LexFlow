"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/shared/providers/AuthProvider";
import { Spinner } from "@/shared/components/ui/Spinner";

export function AdminRoute({ children }: { children: React.ReactNode }) {
  const { status } = useAuth();
  const router = useRouter();

  useEffect(() => {
    if (status === "unauthenticated") router.replace("/admin/login");
  }, [status, router]);

  if (status !== "authenticated") {
    return (
      <div className="grid h-[60vh] place-items-center">
        <Spinner className="text-2xl" />
      </div>
    );
  }

  return <>{children}</>;
}

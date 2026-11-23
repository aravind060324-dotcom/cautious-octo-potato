import { Suspense } from "react";
import { HomeClient } from "@/components/HomeClient";

export default function HomePage() {
  return (
    <Suspense
      fallback={
        <p className="status-banner">Loading Bangalore Bites…</p>
      }
    >
      <HomeClient />
    </Suspense>
  );
}

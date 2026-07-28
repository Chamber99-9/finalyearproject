import { Suspense } from "react";

import { AppShell } from "@/components/AppShell";
import { PaymentReturn } from "@/components/PaymentReturn";

export default function PaymentReturnPage() {
  return (
    <AppShell>
      <Suspense fallback={null}>
        <PaymentReturn />
      </Suspense>
    </AppShell>
  );
}

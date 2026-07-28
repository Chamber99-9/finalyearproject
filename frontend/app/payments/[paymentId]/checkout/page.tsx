import { AppShell } from "@/components/AppShell";
import { PaymentCheckout } from "@/components/PaymentCheckout";

type PageProps = { params: Promise<{ paymentId: string }> };

export default async function CheckoutPage({ params }: PageProps) {
  const { paymentId } = await params;
  return (
    <AppShell>
      <PaymentCheckout paymentId={paymentId} />
    </AppShell>
  );
}

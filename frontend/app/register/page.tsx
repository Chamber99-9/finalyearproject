import { AppShell } from "@/components/AppShell";
import { AuthPanel } from "@/components/AuthPanel";

export default function RegisterPage() {
  return (
    <AppShell>
      <AuthPanel mode="register" />
    </AppShell>
  );
}


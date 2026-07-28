import { AppShell } from "@/components/AppShell";
import { AuthPanel } from "@/components/AuthPanel";

export default function LoginPage() {
  return (
    <AppShell>
      <AuthPanel mode="login" />
    </AppShell>
  );
}


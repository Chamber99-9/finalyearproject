import { AppShell } from "@/components/AppShell";
import { OfficerApplicationReview } from "@/components/OfficerApplicationReview";

type OfficerApplicationReviewPageProps = {
  params: Promise<{
    applicationId: string;
  }>;
};

export default async function OfficerApplicationReviewPage({
  params
}: OfficerApplicationReviewPageProps) {
  const { applicationId } = await params;

  return (
    <AppShell>
      <OfficerApplicationReview applicationId={applicationId} />
    </AppShell>
  );
}

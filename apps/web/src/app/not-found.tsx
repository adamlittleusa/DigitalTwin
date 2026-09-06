import Link from "next/link";
import { PageHeader } from "@/components/PageHeader";

export default function NotFound() {
  return (
    <div className="container">
      <PageHeader eyebrow="404" title="Not here" lede="That page does not exist." />
      <p className="page-section">
        <Link href="/">Back to the gallery</Link>
      </p>
    </div>
  );
}

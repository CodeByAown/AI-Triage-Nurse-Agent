import { redirect } from "next/navigation";

// /reports (index) redirects to /history which is the canonical assessment list
export default function ReportsIndexPage() {
  redirect("/history");
}

import { cookies } from "next/headers";
import { redirect } from "next/navigation";
import { WorkspaceShell } from "@/components/workspace-shell";

export default async function HomePage() {
  const cookieStore = await cookies();
  if (!cookieStore.get("lsa_access")) redirect("/sign-in");
  const role = cookieStore.get("lsa_role")?.value ?? "lecturer";
  return <WorkspaceShell activeRole={role} />;
}

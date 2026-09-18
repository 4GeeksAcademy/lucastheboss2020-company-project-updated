import AuthGuard from "../../AuthGuard";

export default function BackofficeLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}

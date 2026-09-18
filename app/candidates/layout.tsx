import AuthGuard from "../AuthGuard";

export default function CandidatesLayout({ children }: { children: React.ReactNode }) {
  return <AuthGuard>{children}</AuthGuard>;
}

import { useEffect } from "react";
import { useAuth } from "@/auth/AuthProvider";
import { LoginForm } from "@/components/LoginForm";
import { PublicLayout } from "@/components/PublicLayout";
import { navigate } from "@/router";
import { strings } from "@/strings";

export function LoginScreen() {
  const { status } = useAuth();

  useEffect(() => {
    if (status === "authenticated") navigate("/", true); // already signed in
  }, [status]);

  return (
    <PublicLayout>
      <h1 className="mb-4 text-xl font-semibold">{strings.auth.signInHeading}</h1>
      <LoginForm onSignedIn={() => navigate("/")} />
    </PublicLayout>
  );
}

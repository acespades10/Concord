"use client";
import { createContext, useContext, useEffect, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { api, ApiError, setCsrf, type Session, type User } from "@/lib/api";
import { Button } from "./ui/button";

const UserContext = createContext<User | null>(null);
export function useUser() {
  const user = useContext(UserContext);
  if (!user) throw new Error("Missing authenticated user");
  return user;
}
export function Loading({
  label = "Loading your workspace…",
}: {
  label?: string;
}) {
  return (
    <div className="loading-state" role="status">
      <span className="spinner" />
      {label}
    </div>
  );
}
export function ErrorState({
  error,
  retry,
}: {
  error: Error;
  retry?: () => void;
}) {
  return (
    <div className="empty-state" role="alert">
      <h2>We couldn’t load this page</h2>
      <p>{error.message}</p>
      {retry && (
        <Button variant="outline" onClick={retry}>
          Try again
        </Button>
      )}
    </div>
  );
}

export function AuthGate({ children }: { children: ReactNode }) {
  const router = useRouter();
  const session = useQuery({
    queryKey: ["session"],
    queryFn: async () => {
      const data = await api<Session>("/auth/session");
      setCsrf(data.csrf);
      return data;
    },
    staleTime: 60000,
  });
  useEffect(() => {
    if (session.error instanceof ApiError && session.error.status === 401)
      router.replace("/login");
  }, [session.error, router]);
  if (
    session.isPending ||
    (session.error instanceof ApiError && session.error.status === 401)
  )
    return <Loading />;
  if (session.error)
    return (
      <ErrorState error={session.error} retry={() => void session.refetch()} />
    );
  return (
    <UserContext.Provider value={session.data.user}>
      {children}
    </UserContext.Provider>
  );
}

export function RoleGate({
  roles,
  children,
}: {
  roles: User["role"][];
  children: ReactNode;
}) {
  const user = useUser();
  if (!roles.includes(user.role))
    return (
      <div className="empty-state">
        <h2>This workspace is for reviewers</h2>
        <p>Your annotation projects are available from the Projects page.</p>
        <Button asChild>
          <Link href="/projects">Back to projects</Link>
        </Button>
      </div>
    );
  return children;
}

"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { X, CircleCheck, CircleAlert } from "lucide-react";

const NoticeContext = createContext<(message: string, error?: boolean) => void>(
  () => {},
);
export const useNotice = () => useContext(NoticeContext);
export function Providers({ children }: { children: ReactNode }) {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 15000,
            retry: false,
            refetchOnWindowFocus: true,
          },
        },
      }),
  );
  const [notice, setNotice] = useState<{
    message: string;
    error: boolean;
  } | null>(null);
  return (
    <QueryClientProvider client={client}>
      <NoticeContext.Provider
        value={(message, error = false) => setNotice({ message, error })}
      >
        {children}
        {notice && (
          <div
            className={`toast ${notice.error ? "toast-error" : ""}`}
            role={notice.error ? "alert" : "status"}
          >
            {notice.error ? (
              <CircleAlert size={20} />
            ) : (
              <CircleCheck size={20} />
            )}
            <span>{notice.message}</span>
            <button
              aria-label="Dismiss notification"
              onClick={() => setNotice(null)}
            >
              <X size={16} />
            </button>
          </div>
        )}
      </NoticeContext.Provider>
    </QueryClientProvider>
  );
}

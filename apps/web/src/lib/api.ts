import type { components } from "./api-types";

export type User = components["schemas"]["UserOut"];
export type Project = components["schemas"]["ProjectOut"];
export type ProjectConfig = components["schemas"]["ProjectConfig"];
export type Assignment = components["schemas"]["AssignmentOut"];
export type Metrics = components["schemas"]["MetricsOut"];
export type ReviewItem = components["schemas"]["ReviewItem"];
export type Span = components["schemas"]["Span"];
export type Payload =
  | components["schemas"]["RatingPayload"]
  | components["schemas"]["ABPayload"]
  | components["schemas"]["NERPayload"];
export type SaveResult = components["schemas"]["SaveOut"];
export type Session = components["schemas"]["SessionOut"];
let csrf = "";
export function setCsrf(token: string) {
  csrf = token;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof FormData))
    headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET")
    headers.set("X-CSRF-Token", csrf);
  const response = await fetch(`/api/v1${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
    cache: "no-store",
  });
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const detail = data.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.errors
          ? `${detail.message}\n${detail.errors.map((e: { row: number; message: string }) => `Row ${e.row}: ${e.message}`).join("\n")}`
          : Array.isArray(detail)
            ? detail.map((e: { msg: string }) => e.msg).join("; ")
            : "Something went wrong. Please try again.";
    throw new ApiError(response.status, message);
  }
  return response.json();
}

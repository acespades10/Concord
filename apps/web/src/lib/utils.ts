import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
export const percent = (n: number) => `${Math.round(n * 100)}%`;
export const modeNames = {
  rating: "Response rating",
  ner: "Entity annotation",
  ab: "A/B comparison",
};

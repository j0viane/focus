import { validateToken } from "../authUtils";

export function renderSession(token: string): string {
  if (!validateToken(token)) {
    return "Unauthorized";
  }
  return "Session active";
}

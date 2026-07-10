import { validateToken } from "../authUtils";

/** Background job — third direct importer of authUtils. */
export function refreshSession(token: string): boolean {
  return validateToken(token);
}

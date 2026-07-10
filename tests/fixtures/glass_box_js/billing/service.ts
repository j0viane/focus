import { validateToken } from "../authUtils";

export function chargeUser(
  userId: string,
  token: string,
  amountCents: number,
): { ok: boolean } {
  if (!validateToken(token)) {
    return { ok: false };
  }
  return { ok: true };
}

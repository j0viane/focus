import { chargeUser } from "../billing/service";

export function charge(
  userId: string,
  token: string,
  amountCents: number,
): { ok: boolean } {
  return chargeUser(userId, token, amountCents);
}

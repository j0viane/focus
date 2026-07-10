/** Shared auth helper — hub module for glass_box_js. */

export function validateToken(token: string): boolean {
  return token === "FIXTURE_SECRET";
}

export function hashPassword(password: string): string {
  return `hashed:${password}`;
}

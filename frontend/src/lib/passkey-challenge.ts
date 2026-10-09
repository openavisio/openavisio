import { createHmac, timingSafeEqual } from "crypto";

const MAX_AGE_MS = 5 * 60 * 1000; // 5 minutes

export function signChallenge(challenge: string, secret: string): string {
  const ts = Date.now().toString();
  const payload = `${ts}.${challenge}`;
  const sig = createHmac("sha256", secret).update(payload).digest("base64url");
  return `${ts}.${challenge}.${sig}`;
}

export function verifyChallenge(signed: string, secret: string): string | null {
  // format: {timestamp}.{challenge}.{sig}
  // challenge is base64url so no dots; split from both ends
  const firstDot = signed.indexOf(".");
  const lastDot = signed.lastIndexOf(".");
  if (firstDot === -1 || firstDot === lastDot) return null;

  const ts = signed.slice(0, firstDot);
  const challenge = signed.slice(firstDot + 1, lastDot);
  const sig = signed.slice(lastDot + 1);

  if (Date.now() - parseInt(ts) > MAX_AGE_MS) return null;

  const payload = `${ts}.${challenge}`;
  const expectedSig = createHmac("sha256", secret).update(payload).digest("base64url");

  try {
    if (!timingSafeEqual(Buffer.from(sig), Buffer.from(expectedSig))) return null;
  } catch {
    return null;
  }

  return challenge;
}

export function verifyChallengeFromCookieHeader(header: string, secret: string): string | null {
  const match = header.match(/(?:^|;\s*)passkey-challenge=([^;]+)/);
  if (!match) return null;
  return verifyChallenge(decodeURIComponent(match[1]), secret);
}

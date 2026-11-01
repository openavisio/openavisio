import NextAuth, { CredentialsSignin, type DefaultSession } from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { verifyChallengeFromCookieHeader } from "@/lib/passkey-challenge";
import { forwardedFor } from "@/lib/forwarded";

declare module "next-auth" {
  interface Session {
    accessToken?: string;
    error?: string;
    user: DefaultSession["user"] & { role?: string };
  }
  interface User {
    role?: string;
    accessToken?: string;
    refreshToken?: string;
    expiresAt?: string;
  }
}

const API = process.env.API_URL || "http://localhost:8000";

// a 429 is not a wrong password; the login form tells the two apart by this code
class RateLimited extends CredentialsSignin {
  code = "rate_limited";
}

export const { handlers, auth, signIn, signOut } = NextAuth({
  trustHost: true,
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        const res = await fetch(`${API}/api/auth/login`, {
          method: "POST",
          headers: { ...(await forwardedFor()), "Content-Type": "application/json" },
          body: JSON.stringify({ email: credentials.email, password: credentials.password }),
        });
        if (res.status === 429) throw new RateLimited();
        if (!res.ok) return null;
        const data = await res.json();
        return {
          id: data.email,
          email: data.email,
          role: data.role,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          expiresAt: data.expires_at,
        };
      },
    }),
    Credentials({
      id: "passkey",
      credentials: {
        credential: { type: "text" },
      },
      async authorize(credentials, req) {
        const cookieHeader = req.headers.get("cookie") ?? "";
        const challenge = verifyChallengeFromCookieHeader(
          cookieHeader,
          process.env.NEXTAUTH_SECRET!
        );
        if (!challenge) return null;

        let assertion: unknown;
        try {
          assertion = JSON.parse(credentials.credential as string);
        } catch {
          return null;
        }

        const res = await fetch(`${API}/api/auth/passkey/authenticate/complete`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ credential: assertion, expected_challenge: challenge }),
        });
        if (!res.ok) return null;
        const data = await res.json();
        return {
          id: data.email,
          email: data.email,
          role: data.role,
          accessToken: data.access_token,
          refreshToken: data.refresh_token,
          expiresAt: data.expires_at,
        };
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      // Initial sign-in: store all fields from the authorize result
      if (user) {
        token.accessToken = user.accessToken;
        token.refreshToken = user.refreshToken;
        token.role = user.role;
        token.expiresAt = user.expiresAt;
        return token;
      }

      // Token still valid (30 s buffer)
      const expiresAt = token.expiresAt as string | undefined;
      if (expiresAt && Date.now() < new Date(expiresAt).getTime() - 30_000) {
        return token;
      }

      // A refresh that already failed stays failed — the refresh token is dead,
      // and retrying it on every request meant a handful of 401s per page load.
      if (token.error) return token;

      // Attempt silent refresh
      try {
        const res = await fetch(`${API}/api/auth/refresh`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ refresh_token: token.refreshToken }),
        });
        if (res.ok) {
          const data = await res.json();
          token.accessToken = data.access_token;
          token.refreshToken = data.refresh_token;
          token.expiresAt = data.expires_at;
          delete token.error;
        } else {
          token.error = "RefreshTokenExpired";
        }
      } catch {
        token.error = "RefreshTokenExpired";
      }

      return token;
    },
    async session({ session, token }) {
      session.accessToken = token.accessToken as string | undefined;
      session.user.role = token.role as string | undefined;
      if (token.error) {
        session.error = token.error as string;
      }
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
  secret: process.env.NEXTAUTH_SECRET,
});

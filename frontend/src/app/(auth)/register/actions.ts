"use server";

const API = process.env.API_URL || "http://localhost:8000";

export async function registerAction(
  token: string,
  firstName: string,
  lastName: string,
  password: string,
  consent: boolean
): Promise<{ error?: string }> {
  let res: Response;
  try {
    res = await fetch(`${API}/api/auth/register`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        token,
        first_name: firstName,
        last_name: lastName,
        password,
        consent,
      }),
    });
  } catch {
    return { error: "Could not reach the server. Please try again." };
  }

  if (res.status === 201) return {};
  if (res.status === 409) return { error: "An account with this email already exists." };
  if (res.status === 422) return { error: "You must consent to the processing of your data to create an account." };
  if (res.status === 400) {
    const data = await res.json().catch(() => ({}));
    const detail: string = data?.detail ?? "";
    if (detail.toLowerCase().includes("expired")) return { error: "This invitation has expired." };
    return { error: "Invalid invitation link." };
  }
  return { error: "Something went wrong. Please try again." };
}

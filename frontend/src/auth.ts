/**
 * Auth headers. With VITE_FIREBASE_* set, signs in anonymously with Firebase and sends the ID token.
 * Without them (local development), sends a stable random X-Dev-User id that the backend accepts
 * only when AUTH_MODE=dev. UNVERIFIED against a live Firebase project; see docs/TASKS.md.
 */
const cfg = {
  apiKey: import.meta.env.VITE_FIREBASE_API_KEY as string | undefined,
  authDomain: import.meta.env.VITE_FIREBASE_AUTH_DOMAIN as string | undefined,
  projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID as string | undefined,
  appId: import.meta.env.VITE_FIREBASE_APP_ID as string | undefined,
};

let tokenProvider: (() => Promise<string>) | null = null;

async function firebaseToken(): Promise<string> {
  if (!tokenProvider) {
    const { initializeApp } = await import("firebase/app");
    const { getAuth, signInAnonymously } = await import("firebase/auth");
    const auth = getAuth(initializeApp(cfg));
    if (!auth.currentUser) await signInAnonymously(auth);
    tokenProvider = async () => (await auth.currentUser!.getIdToken());
  }
  return tokenProvider();
}

function devId(): string {
  let id = localStorage.getItem("aoc-dev-user");
  if (!id) {
    id = "u" + Math.random().toString(36).slice(2, 10);
    localStorage.setItem("aoc-dev-user", id);
  }
  return id;
}

export async function authHeaders(): Promise<Record<string, string>> {
  if (cfg.apiKey && cfg.projectId) return { Authorization: `Bearer ${await firebaseToken()}` };
  return { "X-Dev-User": devId() };
}

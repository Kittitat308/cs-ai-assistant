export const CHAT_SESSION_STORAGE_KEY = "cs-ai-chat-session";

export type StoredRecognizedUser = {
  id: number;
  name: string;
  role: string;
};

export type StoredChatSession = {
  token: string;
  recognizedUser: StoredRecognizedUser | null;
  claimedName: string | null;
  expiresAt: number;
};

export function readStoredChatSession(): StoredChatSession | null {
  const rawSession = window.sessionStorage.getItem(
    CHAT_SESSION_STORAGE_KEY,
  );

  if (!rawSession) {
    return null;
  }

  try {
    const session = JSON.parse(rawSession) as Partial<StoredChatSession>;

    if (
      typeof session.token !== "string"
      || !session.token
      || typeof session.expiresAt !== "number"
      || !Number.isFinite(session.expiresAt)
    ) {
      return null;
    }

    return {
      token: session.token,
      recognizedUser: session.recognizedUser ?? null,
      claimedName: session.claimedName ?? null,
      expiresAt: session.expiresAt,
    };
  } catch {
    return null;
  }
}

export function writeStoredChatSession(session: StoredChatSession) {
  window.sessionStorage.setItem(
    CHAT_SESSION_STORAGE_KEY,
    JSON.stringify(session),
  );
}

export function clearStoredChatSession() {
  window.sessionStorage.removeItem(CHAT_SESSION_STORAGE_KEY);
}

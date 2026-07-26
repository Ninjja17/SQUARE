/**
 * Lightweight session store — persists workflow_id and stage progress
 * in localStorage so the 6-screen journey survives page refreshes.
 */
export interface SessionData {
  workflowId?: string;
  agentsGenerated?: boolean;
  simulationDone?: boolean;
  governanceDone?: boolean;
  riskDone?: boolean;
  roiDone?: boolean;
  reportDone?: boolean;
}

const KEY = "sq_session";

export function getSession(): SessionData {
  if (typeof window === "undefined") return {};
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? "{}");
  } catch {
    return {};
  }
}

export function setSession(patch: Partial<SessionData>): SessionData {
  const current = getSession();
  const next = { ...current, ...patch };
  localStorage.setItem(KEY, JSON.stringify(next));
  return next;
}

export function clearSession() {
  localStorage.removeItem(KEY);
}

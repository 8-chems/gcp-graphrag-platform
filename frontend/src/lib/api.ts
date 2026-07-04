export interface ChatResponse {
  answer: string;
  used_agents: string[];
  sources: { content: string; source: string; score: number }[];
  graph_facts: { subject: string; relation: string; object: string }[];
  trace: { agent: string; action: string; detail: string }[];
  session_id: string;
}

const API_BASE = import.meta.env.VITE_API_URL ?? "";

async function authHeader(getToken: () => Promise<string | null>): Promise<HeadersInit> {
  const token = await getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

export async function sendChatMessage(
  question: string,
  sessionId: string | null,
  getToken: () => Promise<string | null>
): Promise<ChatResponse> {
  const headers = await authHeader(getToken);
  const response = await fetch(`${API_BASE}/api/v1/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...headers },
    body: JSON.stringify({ question, session_id: sessionId }),
  });

  if (!response.ok) {
    throw new Error(`Chat request failed: ${response.status}`);
  }
  return response.json();
}

export interface MeResponse {
  uid: string;
  email: string;
  is_admin: boolean;
}

export async function getMe(getToken: () => Promise<string | null>): Promise<MeResponse> {
  const headers = await authHeader(getToken);
  const response = await fetch(`${API_BASE}/api/v1/me`, { headers });
  if (!response.ok) {
    throw new Error(`Failed to fetch user role: ${response.status}`);
  }
  return response.json();
}

export interface DocumentSummary {
  id: string;
  filename: string;
  gcs_path: string;
  status: string;
  chunks_created: number;
  entities_extracted: number;
  relationships_extracted: number;
  created_at: string;
}

export async function listDocuments(
  getToken: () => Promise<string | null>
): Promise<DocumentSummary[]> {
  const headers = await authHeader(getToken);
  const response = await fetch(`${API_BASE}/api/v1/admin/documents`, { headers });
  if (!response.ok) {
    throw new Error(`Failed to list documents: ${response.status}`);
  }
  return response.json();
}

export async function deleteDocument(
  documentId: string,
  getToken: () => Promise<string | null>
): Promise<void> {
  const headers = await authHeader(getToken);
  const response = await fetch(`${API_BASE}/api/v1/admin/documents/${documentId}`, {
    method: "DELETE",
    headers,
  });
  if (!response.ok) {
    throw new Error(`Failed to delete document: ${response.status}`);
  }
}

export async function uploadDocument(
  file: File,
  getToken: () => Promise<string | null>
) {
  const headers = await authHeader(getToken);
  const form = new FormData();
  form.append("file", file);

  const response = await fetch(`${API_BASE}/api/v1/admin/documents/upload`, {
    method: "POST",
    headers,
    body: form,
  });

  if (!response.ok) {
    throw new Error(`Upload failed: ${response.status}`);
  }
  return response.json();
}

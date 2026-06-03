import axios, { AxiosInstance, AxiosError } from "axios";
import type {
  Assessment,
  ConversationMessage,
  DashboardStats,
  Patient,
  TokenResponse,
  TriageMessageResponse,
  TriageReport,
  User,
} from "@/types";

// Allow request configs to opt out of the global 401→signin redirect (used by
// soft auth probes on public pages). Declared here so it's strongly typed
// everywhere instead of suppressed with @ts-expect-error.
declare module "axios" {
  export interface AxiosRequestConfig {
    _skipAuthRedirect?: boolean;
  }
}

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Axios instance ────────────────────────────────────────────────────────
const api: AxiosInstance = axios.create({
  baseURL: `${API_URL}/api/v1`,
  headers: { "Content-Type": "application/json" },
  timeout: 30000,
});

// ── Token management ─────────────────────────────────────────────────────
export function setAuthToken(token: string | null) {
  if (token) {
    api.defaults.headers.common["Authorization"] = `Bearer ${token}`;
    if (typeof window !== "undefined") {
      localStorage.setItem("access_token", token);
    }
  } else {
    delete api.defaults.headers.common["Authorization"];
    if (typeof window !== "undefined") {
      localStorage.removeItem("access_token");
      localStorage.removeItem("refresh_token");
    }
  }
}

export function loadStoredToken() {
  if (typeof window !== "undefined") {
    const token = localStorage.getItem("access_token");
    if (token) setAuthToken(token);
  }
}

// Endpoints where a 401 is an expected, in-page result (wrong password, etc.)
// — never auto-refresh or redirect for these; let the calling page show the error.
const AUTH_ENDPOINTS = ["/auth/login", "/auth/register", "/auth/refresh", "/auth/logout"];

function isAuthEndpoint(url?: string): boolean {
  return !!url && AUTH_ENDPOINTS.some((e) => url.includes(e));
}

function onAuthPage(): boolean {
  return (
    typeof window !== "undefined" && window.location.pathname.startsWith("/auth/")
  );
}

// ── Response interceptor: auto-refresh on 401 (protected requests only) ────
api.interceptors.response.use(
  (res) => res,
  async (error: AxiosError & { config?: { _retried?: boolean; _skipAuthRedirect?: boolean } }) => {
    const status = error.response?.status;
    const reqUrl = error.config?.url;

    // Do not intercept auth-endpoint 401s — those are handled by the page.
    if (status !== 401 || typeof window === "undefined" || isAuthEndpoint(reqUrl)) {
      return Promise.reject(error);
    }

    // Soft checks (e.g. the public homepage probing auth state) must never bounce
    // the user to /auth/signin. Reject quietly so the caller can decide.
    if (error.config?._skipAuthRedirect) {
      return Promise.reject(error);
    }

    // A protected request failed with 401. Try one refresh.
    const refreshToken = localStorage.getItem("refresh_token");
    if (refreshToken && error.config && !error.config._retried) {
      try {
        error.config._retried = true;
        const { data } = await axios.post<TokenResponse>(
          `${API_URL}/api/v1/auth/refresh`,
          { refresh_token: refreshToken }
        );
        setAuthToken(data.access_token);
        localStorage.setItem("refresh_token", data.refresh_token);
        error.config.headers["Authorization"] = `Bearer ${data.access_token}`;
        return api.request(error.config);
      } catch {
        // refresh failed — fall through to sign-out handling
      }
    }

    // Session is genuinely invalid. Clear tokens; only redirect if the user
    // is on a protected page (never bounce them around the auth pages).
    setAuthToken(null);
    if (!onAuthPage()) {
      window.location.href = "/auth/signin";
    }
    return Promise.reject(error);
  }
);

// ── Friendly error messages ─────────────────────────────────────────────────
// Single place that turns ANY thrown error (axios/network/timeout/unknown) into
// a calm, user-safe sentence. Never leaks stack traces, URLs, or server internals.
export function getErrorMessage(err: unknown, fallback = "Something went wrong. Please try again."): string {
  if (axios.isAxiosError(err)) {
    // No response → the request never reached the server.
    if (!err.response) {
      if (err.code === "ECONNABORTED") return "The request timed out. Please check your connection and try again.";
      return "We couldn't reach the server. Please check your connection and try again.";
    }

    const status = err.response.status;
    const detail = (err.response.data as { detail?: unknown } | undefined)?.detail;

    // FastAPI sometimes returns `detail` as a validation-error array — flatten it.
    if (Array.isArray(detail)) {
      const first = detail[0] as { msg?: string } | undefined;
      if (first?.msg) return first.msg;
    } else if (typeof detail === "string" && detail.trim()) {
      return detail;
    }

    // Status-based fallbacks so the user always sees something sensible.
    switch (status) {
      case 400: return "That request couldn't be processed. Please review your input.";
      case 401: return "Your session has expired or your credentials are invalid. Please sign in again.";
      case 403: return "You don't have permission to do that.";
      case 404: return "We couldn't find what you were looking for.";
      case 409: return "That item already exists.";
      case 422: return "Some of the information provided is invalid. Please review and try again.";
      case 429: return "Too many requests. Please wait a moment and try again.";
      default:
        if (status >= 500) return "The server ran into a problem. Our team has been notified — please try again shortly.";
        return fallback;
    }
  }
  if (err instanceof Error && err.message) return fallback;
  return fallback;
}

// ── Auth ──────────────────────────────────────────────────────────────────
export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const { data } = await api.post<TokenResponse>("/auth/login", { email, password });
    return data;
  },

  register: async (payload: {
    email: string;
    password: string;
    first_name: string;
    last_name: string;
    organization_name?: string;
  }): Promise<TokenResponse> => {
    const { data } = await api.post<TokenResponse>("/auth/register", payload);
    return data;
  },

  me: async (): Promise<User> => {
    const { data } = await api.get<User>("/auth/me");
    return data;
  },

  // Like me(), but never triggers the global 401 redirect — for public pages
  // (e.g. the homepage) that only want to reflect auth state in the UI.
  meSoft: async (): Promise<User> => {
    const { data } = await api.get<User>("/auth/me", {
      _skipAuthRedirect: true,
    });
    return data;
  },

  updateMe: async (payload: {
    first_name?: string;
    last_name?: string;
    phone?: string;
    avatar_url?: string;
  }): Promise<User> => {
    const { data } = await api.patch<User>("/auth/me", payload);
    return data;
  },

  changePassword: async (current_password: string, new_password: string): Promise<void> => {
    await api.post("/auth/change-password", { current_password, new_password });
  },

  logout: async (): Promise<void> => {
    try {
      await api.post("/auth/logout");
    } finally {
      setAuthToken(null);
    }
  },
};

// ── Patients ──────────────────────────────────────────────────────────────
export const patientsApi = {
  create: async (payload: Partial<Patient>): Promise<Patient> => {
    const { data } = await api.post<Patient>("/patients/", payload);
    return data;
  },

  list: async (params?: { page?: number; size?: number; search?: string }) => {
    const { data } = await api.get<{ items: Patient[]; total: number; pages: number }>(
      "/patients/",
      { params }
    );
    return data;
  },

  get: async (id: string): Promise<Patient> => {
    const { data } = await api.get<Patient>(`/patients/${id}`);
    return data;
  },

  update: async (id: string, payload: Partial<Patient>): Promise<Patient> => {
    const { data } = await api.patch<Patient>(`/patients/${id}`, payload);
    return data;
  },
};

// ── Triage ────────────────────────────────────────────────────────────────
export const triageApi = {
  listAssessments: async (params?: {
    page?: number;
    size?: number;
    status?: string;
  }): Promise<{ items: Assessment[]; total: number; pages: number }> => {
    const { data } = await api.get("/triage/assessments", { params });
    return data;
  },

  startSession: async (patient_id: string, chief_complaint?: string): Promise<Assessment> => {
    const { data } = await api.post<Assessment>("/triage/sessions", {
      patient_id,
      chief_complaint,
    });
    return data;
  },

  sendMessage: async (
    session_token: string,
    message: string
  ): Promise<TriageMessageResponse> => {
    const { data } = await api.post<TriageMessageResponse>("/triage/message", {
      session_token,
      message,
    });
    return data;
  },

  startAnonymousSession: async (): Promise<{ session_token: string; assessment_id: string }> => {
    const { data } = await api.post("/triage/anonymous/start");
    return data;
  },

  sendAnonymousMessage: async (
    session_token: string,
    message: string
  ): Promise<TriageMessageResponse> => {
    const { data } = await api.post<TriageMessageResponse>("/triage/anonymous/message", {
      session_token,
      message,
    });
    return data;
  },

  getConversation: async (session_token: string): Promise<ConversationMessage[]> => {
    const { data } = await api.get<ConversationMessage[]>(
      `/triage/sessions/${session_token}/conversation`
    );
    return data;
  },

  getReport: async (assessment_id: string, session_token?: string): Promise<TriageReport> => {
    // session_token authorizes anonymous access to its own report; authenticated
    // clinic users are authorized via their JWT + organization scope instead.
    const { data } = await api.get<TriageReport>(`/triage/reports/${assessment_id}`, {
      params: session_token ? { session_token } : undefined,
    });
    return data;
  },

  getAssessment: async (assessment_id: string): Promise<Assessment> => {
    const { data } = await api.get<Assessment>(`/triage/sessions/${assessment_id}`);
    return data;
  },
};

// ── Documents (medical file upload + extraction) ────────────────────────────
export interface UploadedDocument {
  id: string;
  patient_id: string;
  doc_type: string;
  original_filename: string;
  status: string;
  extraction?: {
    summary: string | null;
    structured: Array<{ label?: string; value?: string; unit?: string | null }>;
  } | null;
}

export const documentsApi = {
  // Upload from inside an active (anonymous) triage session. Extraction runs
  // server-side; the response includes the structured findings.
  uploadAnonymous: async (
    sessionToken: string,
    file: File,
    docType?: string
  ): Promise<UploadedDocument> => {
    const form = new FormData();
    form.append("file", file);
    form.append("session_token", sessionToken);
    if (docType) form.append("doc_type", docType);
    const { data } = await api.post<UploadedDocument>("/documents/anonymous/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000, // extraction (PDF/vision + structuring) can take a while
    });
    return data;
  },

  // Authenticated upload (provider/patient dashboard), scoped to a patient.
  upload: async (
    patientId: string,
    file: File,
    docType?: string,
    assessmentId?: string
  ): Promise<UploadedDocument> => {
    const form = new FormData();
    form.append("file", file);
    form.append("patient_id", patientId);
    if (docType) form.append("doc_type", docType);
    if (assessmentId) form.append("assessment_id", assessmentId);
    const { data } = await api.post<UploadedDocument>("/documents/upload", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 120000,
    });
    return data;
  },

  list: async (patientId: string): Promise<UploadedDocument[]> => {
    const { data } = await api.get<UploadedDocument[]>("/documents", {
      params: { patient_id: patientId },
    });
    return data;
  },
};

// ── Patient self-service dashboard ──────────────────────────────────────────
export interface PatientFact {
  id: string;
  category: string;
  label: string;
  value: string | null;
  unit: string | null;
  status: string;
  source: string;
  updated_at: string;
}

export interface PatientCareAction {
  id: string;
  type: string;
  description: string;
  status: string;
  due_at: string | null;
}

export interface PatientAssessmentSummary {
  id: string;
  session_token: string;
  chief_complaint: string | null;
  triage_level: string | null;
  status: string | null;
  created_at: string | null;
  completed_at: string | null;
}

export interface PatientDocumentSummary {
  id: string;
  doc_type: string;
  original_filename: string;
  status: string;
  created_at: string | null;
}

export interface PatientTimelineEvent {
  id: string;
  event_type: string;
  title: string;
  description: string | null;
  occurred_at: string;
  severity: string | null;
  source_type: string | null;
}

export interface PatientDashboard {
  patient: {
    id?: string;
    first_name: string | null;
    last_name: string | null;
    age?: number | null;
    biological_sex?: string | null;
  } | null;
  facts: PatientFact[];
  open_actions: PatientCareAction[];
  assessments: PatientAssessmentSummary[];
  documents: PatientDocumentSummary[];
  timeline: PatientTimelineEvent[];
}

export const patientApi = {
  // The authenticated patient's own dashboard payload (profile + remembered
  // history + assessments + documents + timeline) in a single call.
  mySummary: async (): Promise<PatientDashboard> => {
    const { data } = await api.get<PatientDashboard>("/patients/me/summary");
    return data;
  },
};

// ── Voice (speech-to-text) ──────────────────────────────────────────────────
export const voiceApi = {
  // Uploads a recorded audio blob and returns the transcribed text. A longer
  // timeout than normal requests — transcription of a clip can take a few seconds.
  transcribe: async (blob: Blob, filename = "recording.webm", sessionToken?: string): Promise<string> => {
    const form = new FormData();
    form.append("file", blob, filename);
    // When tied to a triage session, the backend also records the transcript as a
    // voice observation in patient memory (Phase 5).
    if (sessionToken) form.append("session_token", sessionToken);
    // Let the browser set the multipart boundary; axios strips the JSON default
    // Content-Type for FormData bodies automatically.
    const { data } = await api.post<{ text: string }>("/voice/transcribe", form, {
      headers: { "Content-Type": "multipart/form-data" },
      timeout: 60000,
    });
    return data.text ?? "";
  },
};

// ── Analytics ─────────────────────────────────────────────────────────────
export const analyticsApi = {
  getDashboard: async (days = 30): Promise<DashboardStats> => {
    const { data } = await api.get<DashboardStats>("/analytics/dashboard", {
      params: { days },
    });
    return data;
  },

  getRiskBreakdown: async (days = 30) => {
    const { data } = await api.get("/analytics/risk-breakdown", { params: { days } });
    return data;
  },
};

// ── Admin ──────────────────────────────────────────────────────────────────
export const adminApi = {
  listUsers: async (params?: { page?: number; size?: number; search?: string }) => {
    const { data } = await api.get("/admin/users", { params });
    return data;
  },

  updateUserRole: async (user_id: string, role: string) => {
    const { data } = await api.patch(`/admin/users/${user_id}/role`, null, {
      params: { role },
    });
    return data;
  },

  deactivateUser: async (user_id: string) => {
    const { data } = await api.patch(`/admin/users/${user_id}/deactivate`);
    return data;
  },

  getAuditLogs: async (params?: { page?: number; size?: number; action?: string }) => {
    const { data } = await api.get("/admin/audit-logs", { params });
    return data;
  },

  getOverview: async () => {
    const { data } = await api.get("/admin/overview");
    return data;
  },
};

export default api;

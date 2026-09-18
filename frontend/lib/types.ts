export interface ApiError {
  code: string;
  message: string;
  details: Record<string, unknown> | Array<unknown>;
}

export interface ApiErrorResponse {
  error: ApiError;
}

export interface User {
  id: string;
  email: string;
  role: string;
  companyId: string;
  isActive: boolean;
  createdAt: string;
}

export interface Company {
  id: string;
  name: string;
  slug: string;
  createdAt: string;
}

export interface RegisterPayload {
  companyName: string;
  email: string;
  password: string;
}

export interface LoginPayload {
  email: string;
  password: string;
}

export interface AuthResponse {
  user: User;
  company: Company;
  accessToken: string;
}

export interface RefreshResponse {
  accessToken: string;
}

export interface MeResponse {
  user: User;
  company: Company;
}

export interface CsrfResponse {
  csrfToken: string;
}

export interface Pagination {
  page: number;
  pageSize: number;
  totalItems: number;
  totalPages: number;
}

export interface PaginatedResponse<T> {
  data: T[];
  pagination: Pagination;
}

export type TenderStatus = "PENDING" | "PROCESSING" | "PROCESSED" | "FAILED";

export interface Tender {
  id: string;
  title: string;
  description: string;
  status: TenderStatus;
  fileSize: number;
  originalFilename: string;
  createdAt: string;
  updatedAt: string;
}

export interface ProcessingStatus {
  tenderId: string;
  status: TenderStatus;
  progress: number;
  processedChunks: number;
  error: { code: string; message: string } | null;
}

export interface SearchResultItem {
  chunkId: string;
  tenderId: string;
  pageNumber: number;
  startCharOffset: number;
  endCharOffset: number;
  snippet: string;
  score: number;
}

export interface Citation {
  documentId?: string;
  chunkId: string;
  pageNumber: number;
  quote: string;
  score?: number;
}

export interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  citations: Citation[];
  createdAt: string;
}

export interface ChatResponse {
  conversationId: string;
  message: Message;
}

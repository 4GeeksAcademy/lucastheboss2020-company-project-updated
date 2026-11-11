export interface ApiErrorPayload {
  error?: string | { field?: string; message?: string };
  detail?: string | Array<{ loc?: (string | number)[]; msg?: string }>;
  message?: string;
  errors?: string[];
}

export class ApiRequestError extends Error {
  readonly status?: number;
  readonly field?: string;

  constructor(message: string, status?: number, field?: string) {
    super(message);
    this.name = "ApiRequestError";
    this.status = status;
    this.field = field;
  }
}

export function userSafeErrorMessage(error: unknown, fallback: string): string {
  return error instanceof ApiRequestError ? error.message : fallback;
}

const FALLBACK_MESSAGES: Record<number, string> = {
  400: "Some submitted information is invalid. Review the form and try again.",
  401: "Your session expired. Please sign in again.",
  403: "You do not have permission to complete this request.",
  404: "The requested item could not be found.",
  409: "This request conflicts with the current account data.",
  413: "The submitted file is too large.",
  415: "This file type is not supported.",
  422: "Some submitted fields are invalid. Review the form and try again.",
};

const FIELD_VALIDATION_MESSAGES: Record<string, string> = {
  email: "Enter a valid email address.",
  password: "Password does not meet the requirements.",
  name: "Check the name field and try again.",
  phone: "Check the phone field and try again.",
  address: "Check the address field and try again.",
};

function isUserSafeServerMessage(value: unknown): value is string {
  return typeof value === "string" && value.length <= 240 &&
    !/(traceback|stack trace|syntaxerror|unexpected token|\bat\s+\S+\s*\(|(?:password|token|authorization)\s*[=:])/i.test(value);
}

function safePayloadMessage(payload: unknown, status: number): { message: string; field?: string } {
  if (status >= 500) {
    return { message: "The service could not complete the request. Please try again." };
  }

  if (!payload || typeof payload !== "object") {
    return { message: FALLBACK_MESSAGES[status] ?? "The request could not be completed. Please try again." };
  }

  const body = payload as ApiErrorPayload;
  const structured = typeof body.error === "object" && body.error !== null ? body.error : undefined;
  let field = structured?.field;
  let validationMessage: string | undefined;
  if (Array.isArray(body.detail) && body.detail.length > 0) {
    const first = body.detail[0];
    const candidateField = Array.isArray(first?.loc) ? String(first.loc[first.loc.length - 1] ?? "") : "";
    if (candidateField) {
      field = candidateField;
      validationMessage = FIELD_VALIDATION_MESSAGES[candidateField] ?? "Check this field and try again.";
    }
  }
  const message =
    validationMessage ||
    (isUserSafeServerMessage(structured?.message) && structured.message) ||
    (isUserSafeServerMessage(body.error) && body.error) ||
    (isUserSafeServerMessage(body.message) && body.message) ||
    (isUserSafeServerMessage(body.detail) && body.detail) ||
    (Array.isArray(body.errors) && isUserSafeServerMessage(body.errors[0]) && body.errors[0]) ||
    (Array.isArray(body.detail) && body.detail.length > 0
      ? "Some submitted fields are invalid. Review the form and try again."
      : undefined);

  return {
    message: message ?? FALLBACK_MESSAGES[status] ?? "The request could not be completed. Please try again.",
    field,
  };
}

export async function parseJsonResponse<T>(response: Response): Promise<T> {
  const rawBody = await response.text().catch(() => "");
  let payload: unknown;
  let malformedJson = false;

  if (rawBody.trim()) {
    try {
      payload = JSON.parse(rawBody);
    } catch {
      malformedJson = true;
    }
  }

  if (!response.ok) {
    const error = safePayloadMessage(payload, response.status);
    throw new ApiRequestError(error.message, response.status, error.field);
  }

  if (malformedJson) {
    throw new ApiRequestError("The service returned an unreadable response.", response.status);
  }

  return payload as T;
}

export async function fetchResponse(input: RequestInfo | URL, init?: RequestInit, timeoutMs = 20_000): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);
  try {
    return await fetch(input, { ...init, signal: init?.signal ?? controller.signal });
  } catch {
    if (controller.signal.aborted) {
      throw new ApiRequestError("The request timed out. Please retry.");
    }
    throw new ApiRequestError("Could not connect to the service. Check your connection and try again.");
  } finally {
    clearTimeout(timeoutId);
  }
}

export async function fetchJson<T>(input: RequestInfo | URL, init?: RequestInit): Promise<T> {
  const response = await fetchResponse(input, init);
  return parseJsonResponse<T>(response);
}

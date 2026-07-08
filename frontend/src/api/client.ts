export const BASE_URL = 'http://localhost:8000/api/v1';

export class ApiError extends Error {
  status: number;
  data?: any;

  constructor(status: number, message: string, data?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.data = data;
  }
}

export async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const token = localStorage.getItem('token');
  
  const headers = new Headers(options.headers);
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`);
  }
  
  // Default to JSON if content-type isn't explicitly set and we're sending a string body
  // Wait, if it's FormData (like for OAuth2 login), we shouldn't set Content-Type.
  if (
    options.body && 
    typeof options.body === 'string' && 
    !headers.has('Content-Type')
  ) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${BASE_URL}${endpoint}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let errorData;
    try {
      errorData = await response.json();
    } catch {
      errorData = { detail: response.statusText };
    }
    
    // Auto-logout on 401 if we have a token
    if (response.status === 401 && token) {
      localStorage.removeItem('token');
      window.dispatchEvent(new Event('auth:unauthorized'));
    }
    
    const msg = errorData.message || errorData.detail || 'An error occurred';
    throw new ApiError(
      response.status,
      typeof msg === 'string' ? msg : JSON.stringify(msg),
      errorData
    );
  }

  // Handle 204 No Content
  if (response.status === 204) {
    return {} as T;
  }

  return response.json() as Promise<T>;
}

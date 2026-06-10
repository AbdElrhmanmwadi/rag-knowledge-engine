# React Auth Integration Brief

Build frontend authentication for the React app using the existing FastAPI backend auth API.

## Backend Base URL

Use an environment variable:

```env
VITE_API_BASE_URL=http://localhost:8000
```

All auth endpoints are mounted directly under:

```text
/auth
```

Project/data endpoints are under:

```text
/api/v1
```

## Auth Endpoints

### Register

```http
POST /auth/register
```

Request body:

```json
{
  "email": "user@example.com",
  "username": "username",
  "password": "password123"
}
```

Success response:

```json
{
  "message": "Check your email"
}
```

After register, show a screen telling the user to check their email.

### Verify Email

```http
GET /auth/verify-email?token=TOKEN_FROM_EMAIL
```

Success response:

```json
{
  "message": "Email verified successfully"
}
```

Create a React route:

```text
/auth/verify-email?token=...
```

This page should read `token` from the query string and call the backend verification endpoint.

### Login

```http
POST /auth/login
```

Request body:

```json
{
  "email": "user@example.com",
  "password": "password123"
}
```

Success response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

Store:

```text
access_token
refresh_token
```

Prefer localStorage for now unless the app already has a safer auth storage pattern.

If backend returns:

```text
401
```

Show invalid email/password.

If backend returns:

```text
403
```

Show email is not verified.

If backend returns:

```text
403
```

with detail `This account uses Google sign-in`, show a message telling the user to use the Google button.

### Google Login

```http
POST /auth/google
```

Request body:

```json
{
  "id_token": "GOOGLE_ID_TOKEN_FROM_FRONTEND"
}
```

Success response (same as login):

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

Frontend setup:

```env
VITE_GOOGLE_CLIENT_ID=your-client-id.apps.googleusercontent.com
```

Use `@react-oauth/google`:

```tsx
import { GoogleLogin, GoogleOAuthProvider } from "@react-oauth/google";

<GoogleOAuthProvider clientId={import.meta.env.VITE_GOOGLE_CLIENT_ID}>
  <GoogleLogin
    onSuccess={async (response) => {
      if (response.credential) {
        await authApi.googleLogin(response.credential);
      }
    }}
    onError={() => {
      // show error
    }}
  />
</GoogleOAuthProvider>
```

Error handling:

| Status | Meaning |
|--------|---------|
| 401 | Invalid or expired Google token |
| 403 | Google email not verified |
| 409 | Email linked to a different Google account |
| 503 | Google login not configured on backend |

### Request Password Reset

```http
POST /auth/request-password-reset
```

Request body:

```json
{
  "email": "user@example.com"
}
```

Success response (always `200`, even if the email does not exist — do not reveal whether an account exists):

```json
{
  "message": "If an account with that email exists, a password reset link has been sent"
}
```

The backend emails the user a link of the form:

```text
{FRONTEND_BASE_URL}/auth/reset-password?token=RESET_TOKEN
```

Notes:

- Google-only accounts (no password) silently receive no email; the response is identical.
- The token expires in 30 minutes and can be used only once.

### Reset Password

```http
POST /auth/reset-password
```

Request body:

```json
{
  "token": "RESET_TOKEN_FROM_EMAIL",
  "new_password": "newPassword123"
}
```

Password rules: 8–128 characters (same as register).

Success response:

```json
{
  "message": "Password has been reset successfully"
}
```

Error handling:

| Status | Detail | Show |
|--------|--------|------|
| 401 | `Token has expired` | "This link has expired. Request a new one." + link to forgot-password |
| 401 | `Invalid or already used reset token` | "This link is invalid or was already used. Request a new one." |
| 401 | `Invalid token` | Same as above |
| 422 | validation error | "Password must be 8–128 characters" |

After a successful reset, all refresh tokens for the user are revoked server-side. Clear any locally stored tokens and send the user to `/login` to sign in with the new password.

Create a React route:

```text
/auth/reset-password?token=...
```

This page reads `token` from the query string and submits it together with the new password.

### Refresh Token

```http
POST /auth/refresh
```

Request body:

```json
{
  "refresh_token": "..."
}
```

Success response:

```json
{
  "access_token": "...",
  "refresh_token": "...",
  "token_type": "bearer"
}
```

Use this when API requests fail with `401` because the access token expired.

### Logout

```http
POST /auth/logout
```

Request body:

```json
{
  "refresh_token": "..."
}
```

After success, clear stored tokens and redirect to login.

## Authorization Header

For protected backend requests, send:

```http
Authorization: Bearer ACCESS_TOKEN
```

Example:

```js
headers: {
  Authorization: `Bearer ${accessToken}`
}
```

## Required React Work

Create or update:

```text
src/api/client.ts
src/api/auth.ts
src/context/AuthContext.tsx
src/pages/Login.tsx
src/pages/Register.tsx
src/pages/VerifyEmail.tsx
src/pages/ForgotPassword.tsx
src/pages/ResetPassword.tsx
src/components/ProtectedRoute.tsx
```

Adapt paths if the React project already has different folders.

## API Client Behavior

Implement a single API client, preferably Axios if already used.

Requirements:

- Automatically attach `Authorization: Bearer <access_token>` to protected requests.
- On `401`, call `/auth/refresh` once using the stored refresh token.
- Retry the original request with the new access token.
- If refresh fails, clear auth state and redirect to `/login`.
- Avoid infinite refresh loops.

## Auth Context

The auth context should expose:

```ts
type AuthContextValue = {
  accessToken: string | null;
  refreshToken: string | null;
  isAuthenticated: boolean;
  login: (email: string, password: string) => Promise<void>;
  loginWithGoogle: (idToken: string) => Promise<void>;
  register: (payload: RegisterPayload) => Promise<void>;
  logout: () => Promise<void>;
};
```

## Protected Routes

Any dashboard, projects, upload, processing, search, chat, voice, or translation page should require auth.

If user is not authenticated, redirect to:

```text
/login
```

## Projects Behavior

The frontend must treat projects as user-owned.

When calling project/data APIs, always include the access token:

```http
Authorization: Bearer ACCESS_TOKEN
```

Do not show global projects from other users.

Once the backend has project ownership fully enforced, project listing and project actions should only return or modify projects belonging to the authenticated user.

## UX Requirements

Login page:

- Email input
- Password input
- Submit button
- Google Sign-In button
- Link to register
- "Forgot password?" link to `/auth/forgot-password`
- Show backend errors cleanly

Forgot password page (`/auth/forgot-password`):

- Email input
- Submit button
- On submit, call `POST /auth/request-password-reset`
- Always show the same success message regardless of whether the email exists
- Disable the submit button for ~30 seconds after sending to discourage spamming
- Link back to login

Reset password page (`/auth/reset-password?token=...`):

- Read `token` from URL; if missing, show an error and a link to forgot-password
- New password input + confirm password input (validate match client-side)
- Validate 8–128 characters before submitting
- On submit, call `POST /auth/reset-password`
- On success, clear any stored tokens, show "Password changed — sign in with your new password", link/redirect to `/login`
- On 401, show the expired/invalid message with a link to request a new email

Register page:

- Email input
- Username input
- Password input
- Submit button
- On success, show "Check your email"

Verify email page:

- Read `token` from URL
- Show loading state
- Show success or error
- Link to login after success

Logout:

- Call backend `/auth/logout` with refresh token
- Clear tokens even if backend logout fails
- Redirect to login

## Example Fetch Flow

```ts
await api.post("/auth/login", {
  email,
  password,
});
```

```ts
await api.get("/api/v1/data/files/123", {
  headers: {
    Authorization: `Bearer ${accessToken}`,
  },
});
```

## Password Reset Implementation Plan

Apply in this order; each step is independently testable.

1. **API layer** (`src/api/auth.ts`): add two functions — no auth header needed, both are public endpoints:

```ts
requestPasswordReset: (email: string) =>
  api.post("/auth/request-password-reset", { email }),

resetPassword: (token: string, newPassword: string) =>
  api.post("/auth/reset-password", { token, new_password: newPassword }),
```

2. **Routes**: register two public routes (outside `ProtectedRoute`):

```text
/auth/forgot-password   -> ForgotPassword.tsx
/auth/reset-password    -> ResetPassword.tsx
```

The second path must match the link in the reset email: `{FRONTEND_BASE_URL}/auth/reset-password?token=...`.

3. **ForgotPassword page**: email form → `requestPasswordReset` → swap form for the generic success message. Treat any `200` as success; never branch on whether the account exists.

4. **ResetPassword page**: read `token` with `useSearchParams()`, password + confirm form, client-side checks (match, 8–128 chars), call `resetPassword`. On success clear auth storage and link to `/login`. On `401` show the expired/invalid message from the error table above.

5. **Login page**: add the "Forgot password?" link under the password field.

6. **Backend env check** (one-time, not React): `FRONTEND_BASE_URL` in `src/.env` currently points to `http://localhost:8000` (the backend itself). Set it to the React dev server origin (e.g. `http://localhost:5173`) and to the real frontend domain in production, then restart the backend — otherwise reset emails link to the wrong place. `RESEND_API_KEY` must also be set or the request endpoint returns `500`.

7. **End-to-end test**: request a reset for a real account → open the email link → set a new password → confirm old password fails, new password logs in, and reusing the same link returns `401`.

## Important Notes

- Do not use Firebase, Auth0, Clerk, or Supabase Auth. The backend owns authentication and token issuance.
- Google Sign-In is supported via `POST /auth/google`; the frontend only sends the Google ID token.
- Resend email verification is already handled by the backend.
- Frontend only calls the verification endpoint when the user opens the verification URL.
- Keep implementation consistent with the existing React app architecture and styling.

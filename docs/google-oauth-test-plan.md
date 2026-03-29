# Google OAuth - Test Plan

## Prerequisites
1. Google OAuth credentials created at console.cloud.google.com
2. `.env` configured with:
   ```
   GOOGLE_CLIENT_ID=<your-client-id>
   GOOGLE_CLIENT_SECRET=<your-client-secret>
   SESSION_SECRET_KEY=<random-string>
   APP_URL=http://localhost:8000
   ```
3. Alembic migration applied: `alembic upgrade head`
4. Local PostgreSQL running

## Test Cases

### 1. Google Login Flow
- [ ] Visit `http://localhost:8000`
- [ ] "Sign in with Google" button is visible
- [ ] Click button → redirects to Google consent screen
- [ ] After Google consent → redirects back to app with token
- [ ] Token is stored in localStorage
- [ ] User info (name, email, avatar) is displayed

### 2. User Persistence
- [ ] Log out (click Logout), then sign in with Google again
- [ ] Same token is returned (not a new one)
- [ ] Previously uploaded files are still there

### 3. `/auth/me` Endpoint
- [ ] `GET /auth/me` with Google-linked token → returns `{anonymous: false, email, name, picture_url}`
- [ ] `GET /auth/me` with anonymous token → returns `{anonymous: true}`

### 4. `/auth/providers` Endpoint
- [ ] Returns `{google: true}` when credentials are configured
- [ ] Returns `{google: false}` when credentials are missing

### 5. Backwards Compatibility
- [ ] `POST /get_token` still works → creates anonymous token
- [ ] Upload/download/search works with anonymous tokens
- [ ] Upload/download/search works with Google-linked tokens
- [ ] Existing anonymous tokens are not broken

### 6. Edge Cases
- [ ] `/auth/google` returns 503 when Google OAuth is not configured
- [ ] Google login button is hidden when OAuth is not configured
- [ ] Multiple Google logins don't create duplicate users

## Production Deployment Checklist
- [ ] Run Alembic migration on production DB (via ECS one-off task)
- [ ] Add env vars to ECS task definition: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `SESSION_SECRET_KEY`, `APP_URL=https://clawbox.ink`
- [ ] Add `https://clawbox.ink/auth/google/callback` to Google OAuth redirect URIs
- [ ] Build and push new Docker image
- [ ] Deploy to ECS
- [ ] Verify Google login on https://clawbox.ink

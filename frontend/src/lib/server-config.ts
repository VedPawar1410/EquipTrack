import "server-only";

/** Where the FastAPI backend lives. Server-side only: the browser never talks to it directly. */
export const API_URL = (process.env.API_URL ?? "http://localhost:8000").replace(/\/$/, "");

/** The JWT lives in an httpOnly cookie: page JavaScript (and so an injected script) can never read it. */
export const TOKEN_COOKIE = "et_token";
export const TOKEN_MAX_AGE_SECONDS = 60 * 60; // matches the API's ACCESS_TOKEN_EXPIRE_MINUTES default

/* The two kinds of failure every view distinguishes. */

/** The reader must sign in (again) before this can succeed. */
export class AuthError extends Error {
  constructor(message) {
    super(message);
    this.name = "AuthError";
  }
}

/** A request failed for another reason: unreachable server, missing data, and so on. */
export class ApiError extends Error {
  constructor(message, status = 0) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

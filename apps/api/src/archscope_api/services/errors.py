"""Errors services raise; the app turns each into an RFC 9457 problem response."""

from __future__ import annotations


class ServiceError(Exception):
    status = 400
    slug = "bad-request"
    title = "Request failed"

    def __init__(self, detail: str = ""):
        super().__init__(detail or self.title)
        self.detail = detail


class NotSignedIn(ServiceError):
    status, slug, title = 401, "not-signed-in", "Sign in to continue"


class SignInFailed(ServiceError):
    status, slug, title = 401, "sign-in-failed", "Email or password is incorrect"


class Forbidden(ServiceError):
    status, slug, title = 403, "forbidden", "You don't have permission to do that"


class NotFound(ServiceError):
    status, slug, title = 404, "not-found", "Not found"


class Conflict(ServiceError):
    status, slug, title = 409, "conflict", "That conflicts with existing data"


class VersionConflict(Conflict):
    slug, title = "version-conflict", "Someone else saved changes first"


class InvalidCode(ServiceError):
    status, slug, title = 400, "invalid-code", "That code isn't right"


class WeakPassword(ServiceError):
    status, slug, title = 422, "weak-password", "Choose a stronger password"


class TooManyRequests(ServiceError):
    status, slug, title = 429, "too-many-requests", "Please wait a moment"


class Unavailable(ServiceError):
    status, slug, title = 503, "unavailable", "Not available on this server"

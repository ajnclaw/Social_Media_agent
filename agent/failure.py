from .task import (
    FAILURE_TRANSIENT,
    FAILURE_RECOVERABLE,
    FAILURE_PERMANENT,
)


class FailureClassifier:

    def classify(self, error, task=None):
        error_text = str(error or "").lower()

        # -----------------------------
        # Transient failures
        # -----------------------------
        transient_keywords = [
            "timeout",
            "timed out",
            "connection",
            "network",
            "temporarily unavailable",
            "rate limit",
            "too many requests",
            "503",
            "502",
            "504",
        ]

        if any(
            keyword in error_text
            for keyword in transient_keywords
        ):
            return FAILURE_TRANSIENT

        # -----------------------------
        # Recoverable failures
        # -----------------------------
        recoverable_keywords = [
            "expected output",
            "verification failed",
            "incorrect output",
            "wrong output",
            "file edited",
            "invalid content",
        ]

        if any(
            keyword in error_text
            for keyword in recoverable_keywords
        ):
            return FAILURE_RECOVERABLE

        # -----------------------------
        # Permanent failures
        # -----------------------------
        permanent_keywords = [
            "permission denied",
            "not found",
            "does not exist",
            "unknown tool",
            "invalid tool",
            "invalid argument",
        ]

        if any(
            keyword in error_text
            for keyword in permanent_keywords
        ):
            return FAILURE_PERMANENT

        # --------------------------------
        # Conservative default
        # --------------------------------
        return FAILURE_PERMANENT
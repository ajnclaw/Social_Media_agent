from agent.failure import FailureClassifier
from agent.task import (
    FAILURE_TRANSIENT,
    FAILURE_RECOVERABLE,
    FAILURE_PERMANENT,
)


def test_classifies_timeout_as_transient():
    classifier = FailureClassifier()

    assert classifier.classify("Connection timed out") == FAILURE_TRANSIENT


def test_classifies_http_5xx_as_transient():
    classifier = FailureClassifier()

    assert classifier.classify("503 Service Unavailable") == FAILURE_TRANSIENT


def test_classifies_server_disconnected_as_transient():
    classifier = FailureClassifier()

    error = "Server disconnected without sending a response."

    assert classifier.classify(error) == FAILURE_TRANSIENT


def test_classification_is_case_insensitive():
    classifier = FailureClassifier()

    assert classifier.classify("CONNECTION TIMED OUT") == FAILURE_TRANSIENT


def test_classifies_verification_mismatch_as_recoverable():
    classifier = FailureClassifier()

    error = "Expected output: 'hello world', but received: 'goodbye world'"

    assert classifier.classify(error) == FAILURE_RECOVERABLE


def test_classifies_verification_failed_as_recoverable():
    classifier = FailureClassifier()

    assert classifier.classify("Verification failed") == FAILURE_RECOVERABLE


def test_classifies_permission_denied_as_permanent():
    classifier = FailureClassifier()

    assert classifier.classify("Permission denied") == FAILURE_PERMANENT


def test_classifies_missing_file_as_permanent():
    classifier = FailureClassifier()

    assert classifier.classify("File does not exist: hello.py") == FAILURE_PERMANENT


def test_unknown_error_defaults_to_permanent():
    classifier = FailureClassifier()

    assert classifier.classify("Something completely unexpected happened") == FAILURE_PERMANENT


def test_none_error_defaults_to_permanent():
    classifier = FailureClassifier()

    assert classifier.classify(None) == FAILURE_PERMANENT


def test_transient_keyword_takes_priority_over_permanent():
    classifier = FailureClassifier()

    # Contains both a transient keyword ("timeout") and a permanent
    # one ("not found") -- transient is checked first and wins.
    error = "Request timeout: resource not found"

    assert classifier.classify(error) == FAILURE_TRANSIENT

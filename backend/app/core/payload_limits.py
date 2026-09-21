"""Resource limits and guards for generic submission payloads.

These limits are the first line of defense against oversized or deeply nested
payloads that could exhaust server memory, applied *before* dynamic field
validation. They are shared by both new-submission and record-edit paths.

Limits are generous for real-world forms but hard caps against abuse:
* at most ``MAX_SUBMISSION_FIELDS`` keys in ``data``
* nesting depth at most ``MAX_PAYLOAD_DEPTH`` levels
* serialized size at most ``MAX_SERIALIZED_PAYLOAD_CHARS`` characters
"""

import json

MAX_SUBMISSION_FIELDS = 100
MAX_PAYLOAD_DEPTH = 8
MAX_SERIALIZED_PAYLOAD_CHARS = 262144  # 256 KiB
MAX_UNCONFIGURED_STRING_LENGTH = 10000

_depth_limit_exceeded = ValueError(
    f"Submission data exceeds the maximum nesting depth of {MAX_PAYLOAD_DEPTH}"
)

_field_limit_exceeded = ValueError(
    f"Submission data exceeds the maximum of {MAX_SUBMISSION_FIELDS} fields"
)


def _measure_depth(root: object) -> int:
    """Measure the deepest container nesting level below ``root``.

    Iterative on purpose: a recursive walker would itself blow the stack on a
    maliciously deep payload before the guard could report a clean error.
    ``root`` itself counts as level 1; a scalar leaf adds nothing.
    """
    max_containers = 0
    stack: list[tuple[object, int]] = [(root, 0)]
    while stack:
        node, containers = stack.pop()
        if isinstance(node, dict) or isinstance(node, list):
            level = containers + 1
            if level > MAX_PAYLOAD_DEPTH:
                return level
            if level > max_containers:
                max_containers = level
            children = node.values() if isinstance(node, dict) else node
            for child in children:
                stack.append((child, level))
    return max_containers


def validate_payload(data: dict) -> dict:
    """Validate generic ``data`` against the resource limits.

    Returns the payload unchanged or raises ``ValueError`` describing the
    violation. The schema layer surfaces these as ``422`` responses.
    """
    if len(data) > MAX_SUBMISSION_FIELDS:
        raise _field_limit_exceeded

    if _measure_depth(data) > MAX_PAYLOAD_DEPTH:
        raise _depth_limit_exceeded

    if len(json.dumps(data)) > MAX_SERIALIZED_PAYLOAD_CHARS:
        raise ValueError(
            "Submission data exceeds the maximum serialized size of "
            f"{MAX_SERIALIZED_PAYLOAD_CHARS} characters"
        )

    return data
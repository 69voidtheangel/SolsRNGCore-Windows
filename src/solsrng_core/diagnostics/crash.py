from __future__ import annotations

import re
import traceback

import requests

from solsrng_core.diagnostics.logger import LOGGER


_SECRET_RE = re.compile(
    r"(https?://(?:discord(?:app)?\.com)/api/webhooks/"
    r"\d+/)[^ \n]+",
    re.IGNORECASE,
)


def _sanitize(text: str) -> str:
    # Never send webhook tokens back to Discord.
    text = _SECRET_RE.sub(
        r"\1[REDACTED]",
        text,
    )

    # Keep reports bounded.
    return text[-5000:]


def send_fatal_report(
    webhook_url: str,
    reason: str,
    *,
    traceback_text: str | None = None,
) -> bool:
    """
    Send one compact fatal diagnostic report.

    This function is intentionally bounded and sanitizes webhook URLs.
    """

    if not webhook_url:
        return False

    recent = LOGGER.recent_text(100)

    body = [
        "🚨 **SolsRNGCore FATAL**",
        "",
        f"**Reason:** {_sanitize(reason)}",
        "",
        "```text",
        _sanitize(LOGGER.system_info()),
        "```",
        "",
        "**Recent diagnostics:**",
        "```text",
        _sanitize(recent),
        "```",
    ]

    if traceback_text:
        body.extend(
            [
                "",
                "**Traceback:**",
                "```text",
                _sanitize(traceback_text),
                "```",
            ]
        )

    payload = {
        "content": "\n".join(body),
        "allowed_mentions": {
            "parse": []
        },
    }

    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=(3, 8),
        )

        return 200 <= response.status_code < 300

    except Exception as exc:
        LOGGER.error(
            f"Unable to send fatal report: {exc}"
        )
        return False


def report_python_exception(
    webhook_url: str,
    exc: BaseException,
) -> None:
    tb = "".join(
        traceback.format_exception(
            type(exc),
            exc,
            exc.__traceback__,
        )
    )

    LOGGER.fatal(
        f"Unhandled Python exception: {exc}"
    )

    send_fatal_report(
        webhook_url,
        "Unhandled Python exception",
        traceback_text=tb,
    )

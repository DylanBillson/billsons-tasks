from urllib.parse import (
    parse_qsl,
    urlencode,
    urlsplit,
    urlunsplit,
)

from fastapi import APIRouter, Request, status
from fastapi.responses import RedirectResponse

from app.schemas.feedback import FeedbackSubmission
from app.services.feedback_service import (
    FeedbackConfigurationError,
    FeedbackDeliveryError,
    FeedbackService,
    FeedbackServiceError,
)
from app.web.dependencies.auth import (
    CurrentUser,
    DatabaseSession,
    get_client_ip_address,
    get_user_agent,
)
from app.web.dependencies.csrf import ValidatedCSRFSession
from app.web.forms.feedback import FeedbackForm


router = APIRouter(
    tags=[
        "feedback",
    ],
)


@router.post(
    "/feedback",
    name="feedback_submit",
)
async def submit_feedback(
    request: Request,
    db: DatabaseSession,
    current_user: CurrentUser,
    auth_session: ValidatedCSRFSession,
) -> RedirectResponse:
    del auth_session

    form_data = await request.form()

    form = FeedbackForm.from_form_data(
        form_data,
    )

    feedback_submission = form.validate()

    redirect_target = _get_safe_return_target(
        request=request,
        supplied_url=form.page_url,
    )

    if feedback_submission is None:
        return _redirect(
            path=redirect_target,
            error=_first_form_error(
                form,
                "Please enter a valid feedback message.",
            ),
        )

    normalised_submission = FeedbackSubmission(
        message=feedback_submission.message,
        page_url=_get_feedback_page_url(
            request=request,
            supplied_url=feedback_submission.page_url,
        ),
    )

    try:
        result = FeedbackService.send_feedback(
            db,
            user=current_user,
            submission=normalised_submission,
            ip_address=get_client_ip_address(
                request,
            ),
            user_agent=get_user_agent(
                request,
            ),
        )

    except FeedbackConfigurationError:
        return _redirect(
            path=redirect_target,
            error=(
                "Feedback email is not currently configured. "
                "Please contact an administrator."
            ),
        )

    except FeedbackDeliveryError:
        return _redirect(
            path=redirect_target,
            error=(
                "Your feedback could not be sent. "
                "Please try again later."
            ),
        )

    except FeedbackServiceError as exc:
        return _redirect(
            path=redirect_target,
            error=str(
                exc,
            ),
        )

    return _redirect(
        path=redirect_target,
        success=(
            "Your feedback was sent successfully. "
            f"Reference: {result.issue_number}."
        ),
    )


def _get_feedback_page_url(
    *,
    request: Request,
    supplied_url: str,
) -> str:
    """
    Return a canonical same-origin absolute URL for the feedback email.

    The browser supplies the page on which the modal was opened, but the
    server does not trust arbitrary external URLs from form data.
    """
    parsed_url = urlsplit(
        supplied_url.strip(),
    )

    if parsed_url.scheme or parsed_url.netloc:
        if not _is_same_origin(
            request=request,
            parsed_url=parsed_url,
        ):
            return (
                str(
                    request.base_url,
                ).rstrip(
                    "/",
                )
                + "/"
            )

        path = parsed_url.path or "/"
        query = parsed_url.query

    else:
        path = parsed_url.path or "/"
        query = parsed_url.query

        if (
            not path.startswith(
                "/",
            )
            or path.startswith(
                "//",
            )
        ):
            path = "/"
            query = ""

    return (
        str(
            request.base_url,
        ).rstrip(
            "/",
        )
        + urlunsplit(
            (
                "",
                "",
                path,
                query,
                "",
            ),
        )
    )


def _get_safe_return_target(
    *,
    request: Request,
    supplied_url: str,
) -> str:
    """
    Convert the submitted page URL into a safe local redirect.

    Fragments are discarded because they are not relevant to the server-side
    redirect.
    """
    parsed_url = urlsplit(
        supplied_url.strip(),
    )

    if parsed_url.scheme or parsed_url.netloc:
        if not _is_same_origin(
            request=request,
            parsed_url=parsed_url,
        ):
            return "/"

    path = parsed_url.path or "/"

    if (
        not path.startswith(
            "/",
        )
        or path.startswith(
            "//",
        )
    ):
        return "/"

    return urlunsplit(
        (
            "",
            "",
            path,
            parsed_url.query,
            "",
        ),
    )


def _is_same_origin(
    *,
    request: Request,
    parsed_url,
) -> bool:
    request_host = request.url.hostname
    supplied_host = parsed_url.hostname

    if supplied_host != request_host:
        return False

    request_port = _effective_port(
        scheme=request.url.scheme,
        port=request.url.port,
    )

    supplied_port = _effective_port(
        scheme=parsed_url.scheme,
        port=parsed_url.port,
    )

    return supplied_port == request_port


def _effective_port(
    *,
    scheme: str,
    port: int | None,
) -> int | None:
    if port is not None:
        return port

    if scheme == "https":
        return 443

    if scheme == "http":
        return 80

    return None


def _redirect(
    *,
    path: str,
    success: str | None = None,
    error: str | None = None,
) -> RedirectResponse:
    parsed_path = urlsplit(
        path,
    )

    query = dict(
        _existing_query_items(
            path,
        ),
    )

    if success:
        query["success"] = success

    if error:
        query["error"] = error

    url = urlunsplit(
        (
            "",
            "",
            parsed_path.path or "/",
            urlencode(
                query,
            ),
            "",
        ),
    )

    return RedirectResponse(
        url=url,
        status_code=status.HTTP_303_SEE_OTHER,
    )


def _existing_query_items(
    path: str,
) -> list[tuple[str, str]]:
    return parse_qsl(
        urlsplit(
            path,
        ).query,
        keep_blank_values=True,
    )


def _first_form_error(
    form: FeedbackForm,
    default: str,
) -> str:
    if form.errors.form_errors:
        return form.errors.form_errors[0]

    for messages in form.errors.field_errors.values():
        if messages:
            return messages[0]

    return default
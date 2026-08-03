document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseConfirmDialogs();
        initialiseAutoDismissFlashMessages();
        initialiseFlashMessageDismissButtons();
        initialiseFormSubmissionProtection();
        initialiseFilterFormPageReset();
    },
);

function initialiseConfirmDialogs() {
    document
        .querySelectorAll("[data-confirm]")
        .forEach(
            (element) => {
                const message =
                    element.dataset.confirm;

                if (!message) {
                    return;
                }

                if (element.matches("form")) {
                    element.addEventListener(
                        "submit",
                        (event) => {
                            if (
                                !window.confirm(
                                    message,
                                )
                            ) {
                                event.preventDefault();
                            }
                        },
                    );

                    return;
                }

                element.addEventListener(
                    "click",
                    (event) => {
                        if (
                            event.defaultPrevented
                        ) {
                            return;
                        }

                        if (
                            !window.confirm(
                                message,
                            )
                        ) {
                            event.preventDefault();
                        }
                    },
                );
            },
        );
}

function initialiseAutoDismissFlashMessages() {
    document
        .querySelectorAll(".flash-message")
        .forEach(
            (message) => {
                if (
                    message.dataset.persist
                    === "true"
                ) {
                    return;
                }

                const delay = parsePositiveInteger(
                    message.dataset.dismissAfter,
                    5000,
                );

                window.setTimeout(
                    () => {
                        dismissFlashMessage(
                            message,
                        );
                    },
                    delay,
                );
            },
        );
}

function initialiseFlashMessageDismissButtons() {
    document
        .querySelectorAll(
            "[data-dismiss-flash]",
        )
        .forEach(
            (button) => {
                button.addEventListener(
                    "click",
                    () => {
                        const message =
                            button.closest(
                                ".flash-message",
                            );

                        if (!message) {
                            return;
                        }

                        dismissFlashMessage(
                            message,
                        );
                    },
                );
            },
        );
}

function dismissFlashMessage(message) {
    if (
        message.classList.contains(
            "flash-message-hidden",
        )
    ) {
        return;
    }

    message.classList.add(
        "flash-message-hidden",
    );

    const removeMessage = () => {
        message.remove();
    };

    message.addEventListener(
        "transitionend",
        removeMessage,
        {
            once: true,
        },
    );

    /*
     * Ensure the hidden message is eventually removed even if its CSS does
     * not currently define a transition.
     */
    window.setTimeout(
        removeMessage,
        500,
    );
}

function initialiseFormSubmissionProtection() {
    document
        .querySelectorAll("form")
        .forEach(
            (form) => {
                if (
                    form.dataset.allowMultipleSubmissions
                    === "true"
                ) {
                    return;
                }

                form.addEventListener(
                    "submit",
                    (event) => {
                        /*
                         * Another handler may have cancelled submission, for
                         * example a confirmation dialog or custom validation.
                         */
                        window.queueMicrotask(
                            () => {
                                if (
                                    event.defaultPrevented
                                    || !form.isConnected
                                ) {
                                    return;
                                }

                                protectSubmittedForm(
                                    form,
                                );
                            },
                        );
                    },
                );
            },
        );
}

function protectSubmittedForm(form) {
    if (
        form.dataset.submissionPending
        === "true"
    ) {
        return;
    }

    form.dataset.submissionPending = "true";

    form
        .querySelectorAll(
            "button[type='submit'], input[type='submit']",
        )
        .forEach(
            (control) => {
                control.disabled = true;
                control.setAttribute(
                    "aria-disabled",
                    "true",
                );

                if (
                    control instanceof HTMLButtonElement
                    && control.dataset.loadingText
                ) {
                    control.dataset.originalText =
                        control.textContent;

                    control.textContent =
                        control.dataset.loadingText;
                }
            },
        );
}

function initialiseFilterFormPageReset() {
    document
        .querySelectorAll(
            "form[data-filter-form], form.filter-panel",
        )
        .forEach(
            (form) => {
                const pageInput = form.querySelector(
                    "[name='page']",
                );

                if (!pageInput) {
                    return;
                }

                form
                    .querySelectorAll(
                        "input, select, textarea",
                    )
                    .forEach(
                        (control) => {
                            if (
                                control.name === "page"
                                || control.type
                                === "hidden"
                            ) {
                                return;
                            }

                            control.addEventListener(
                                "change",
                                () => {
                                    pageInput.value = "1";
                                },
                            );
                        },
                    );
            },
        );
}

function parsePositiveInteger(
    value,
    fallback,
) {
    const parsedValue = Number.parseInt(
        value,
        10,
    );

    if (
        Number.isNaN(
            parsedValue,
        )
        || parsedValue < 1
    ) {
        return fallback;
    }

    return parsedValue;
}
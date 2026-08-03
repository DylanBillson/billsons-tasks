document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseConfirmDialogs();
        initialiseAutoDismissFlashMessages();
        initialiseFormSubmissionProtection();
    },
);

function initialiseConfirmDialogs() {
    document
        .querySelectorAll("[data-confirm]")
        .forEach(
            (element) => {
                element.addEventListener(
                    "submit",
                    (event) => {
                        const message =
                            element.dataset.confirm;

                        if (
                            message
                            && !window.confirm(message)
                        ) {
                            event.preventDefault();
                        }
                    },
                );

                element.addEventListener(
                    "click",
                    (event) => {
                        if (
                            event.target.tagName !== "BUTTON"
                        ) {
                            return;
                        }

                        const message =
                            element.dataset.confirm;

                        if (
                            message
                            && !window.confirm(message)
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
                    message.dataset.persist === "true"
                ) {
                    return;
                }

                window.setTimeout(
                    () => {
                        message.classList.add(
                            "flash-message-hidden",
                        );
                    },
                    5000,
                );
            },
        );
}

function initialiseFormSubmissionProtection() {
    document
        .querySelectorAll("form")
        .forEach(
            (form) => {
                form.addEventListener(
                    "submit",
                    () => {
                        form
                            .querySelectorAll(
                                "button[type='submit']",
                            )
                            .forEach(
                                (button) => {
                                    button.disabled = true;
                                },
                            );
                    },
                    {
                        once: true,
                    },
                );
            },
        );
}
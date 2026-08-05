document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseConfirmDialogs();
        initialiseAutoDismissFlashMessages();
        initialiseFlashMessageDismissButtons();
        initialiseFormSubmissionProtection();
        initialiseFilterFormPageReset();
        initialiseAdministrationMenus();
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
                        if (event.defaultPrevented) {
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
        if (message.isConnected) {
            message.remove();
        }
    };

    message.addEventListener(
        "transitionend",
        removeMessage,
        {
            once: true,
        },
    );

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
                    control.dataset.originalText = (
                        control.textContent
                    );

                    control.textContent = (
                        control.dataset.loadingText
                    );
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

                if (
                    !(
                        pageInput
                        instanceof HTMLInputElement
                    )
                ) {
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
                                || control.type === "hidden"
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


function initialiseAdministrationMenus() {
    const menus = Array.from(
        document.querySelectorAll(
            "details[data-admin-menu]",
        ),
    );

    if (menus.length === 0) {
        return;
    }

    const updateMenuState = (
        menu,
    ) => {
        const toggle = menu.querySelector(
            "[data-admin-menu-toggle]",
        );

        if (
            !(
                toggle
                instanceof HTMLElement
            )
        ) {
            return;
        }

        toggle.setAttribute(
            "aria-expanded",
            menu.open
                ? "true"
                : "false",
        );
    };

    const closeMenu = (
        menu,
        {
            restoreFocus = false,
        } = {},
    ) => {
        if (!menu.open) {
            updateMenuState(
                menu,
            );

            return;
        }

        menu.open = false;

        updateMenuState(
            menu,
        );

        if (restoreFocus) {
            const toggle = menu.querySelector(
                "[data-admin-menu-toggle]",
            );

            if (
                toggle
                instanceof HTMLElement
            ) {
                toggle.focus();
            }
        }
    };

    const closeOtherMenus = (
        currentMenu,
    ) => {
        menus.forEach(
            (menu) => {
                if (
                    menu
                    !== currentMenu
                ) {
                    closeMenu(
                        menu,
                    );
                }
            },
        );
    };

    menus.forEach(
        (menu) => {
            const toggle = menu.querySelector(
                "[data-admin-menu-toggle]",
            );

            const links = Array.from(
                menu.querySelectorAll(
                    ".app-admin-menu-link",
                ),
            );

            updateMenuState(
                menu,
            );

            menu.addEventListener(
                "toggle",
                () => {
                    updateMenuState(
                        menu,
                    );

                    if (menu.open) {
                        closeOtherMenus(
                            menu,
                        );
                    }
                },
            );

            if (
                toggle
                instanceof HTMLElement
            ) {
                toggle.addEventListener(
                    "keydown",
                    (event) => {
                        if (
                            event.key
                            === "ArrowDown"
                            && menu.open
                        ) {
                            const firstLink =
                                links[0];

                            if (
                                firstLink
                                instanceof HTMLElement
                            ) {
                                event.preventDefault();

                                firstLink.focus();
                            }

                            return;
                        }

                        if (
                            event.key
                            === "Escape"
                            && menu.open
                        ) {
                            event.preventDefault();

                            closeMenu(
                                menu,
                                {
                                    restoreFocus: true,
                                },
                            );
                        }
                    },
                );
            }

            links.forEach(
                (
                    link,
                    index,
                ) => {
                    link.addEventListener(
                        "keydown",
                        (event) => {
                            if (
                                event.key
                                === "Escape"
                            ) {
                                event.preventDefault();

                                closeMenu(
                                    menu,
                                    {
                                        restoreFocus: true,
                                    },
                                );

                                return;
                            }

                            if (
                                event.key
                                !== "ArrowDown"
                                && event.key
                                !== "ArrowUp"
                            ) {
                                return;
                            }

                            event.preventDefault();

                            const direction = (
                                event.key
                                === "ArrowDown"
                                    ? 1
                                    : -1
                            );

                            const targetIndex = (
                                index
                                + direction
                                + links.length
                            ) % links.length;

                            const targetLink =
                                links[
                                    targetIndex
                                ];

                            if (
                                targetLink
                                instanceof HTMLElement
                            ) {
                                targetLink.focus();
                            }
                        },
                    );
                },
            );
        },
    );

    document.addEventListener(
        "click",
        (event) => {
            if (
                !(
                    event.target
                    instanceof Node
                )
            ) {
                return;
            }

            menus.forEach(
                (menu) => {
                    if (
                        !menu.contains(
                            event.target,
                        )
                    ) {
                        closeMenu(
                            menu,
                        );
                    }
                },
            );
        },
    );

    document.addEventListener(
        "keydown",
        (event) => {
            if (
                event.key
                !== "Escape"
            ) {
                return;
            }

            const openMenu = menus.find(
                (menu) => menu.open,
            );

            if (!openMenu) {
                return;
            }

            event.preventDefault();

            closeMenu(
                openMenu,
                {
                    restoreFocus: true,
                },
            );
        },
    );
}


function parsePositiveInteger(
    value,
    fallback,
) {
    const parsedValue =
        Number.parseInt(
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
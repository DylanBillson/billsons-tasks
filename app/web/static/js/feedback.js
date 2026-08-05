document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseFeedbackModal();
    },
);

function initialiseFeedbackModal() {
    const modal = document.querySelector(
        "[data-feedback-modal]",
    );

    if (!(modal instanceof HTMLDialogElement)) {
        return;
    }

    const openButtons = document.querySelectorAll(
        "[data-feedback-open]",
    );

    const closeButtons = modal.querySelectorAll(
        "[data-feedback-close]",
    );

    const form = modal.querySelector(
        "[data-feedback-form]",
    );

    const pageUrlInput = modal.querySelector(
        "[data-feedback-page-url]",
    );

    const messageInput = modal.querySelector(
        "[data-feedback-message]",
    );

    const characterCount = modal.querySelector(
        "[data-feedback-character-count]",
    );

    let previouslyFocusedElement = null;

    const updatePageUrl = () => {
        if (!(pageUrlInput instanceof HTMLInputElement)) {
            return;
        }

        pageUrlInput.value = window.location.href;
    };

    const updateCharacterCount = () => {
        if (
            !(messageInput instanceof HTMLTextAreaElement)
            || !(characterCount instanceof HTMLElement)
        ) {
            return;
        }

        const maximumLength = (
            messageInput.maxLength > 0
                ? messageInput.maxLength
                : 5000
        );

        characterCount.textContent = (
            `${messageInput.value.length} / ${maximumLength}`
        );
    };

    const openModal = () => {
        if (modal.open) {
            return;
        }

        previouslyFocusedElement = (
            document.activeElement instanceof HTMLElement
                ? document.activeElement
                : null
        );

        updatePageUrl();
        updateCharacterCount();

        modal.showModal();

        window.requestAnimationFrame(
            () => {
                if (
                    messageInput
                    instanceof HTMLTextAreaElement
                ) {
                    messageInput.focus();
                }
            },
        );
    };

    const closeModal = () => {
        if (!modal.open) {
            return;
        }

        modal.close();
    };

    const restoreFocus = () => {
        if (
            previouslyFocusedElement
            && previouslyFocusedElement.isConnected
        ) {
            previouslyFocusedElement.focus();
        }

        previouslyFocusedElement = null;
    };

    openButtons.forEach(
        (button) => {
            button.addEventListener(
                "click",
                openModal,
            );
        },
    );

    closeButtons.forEach(
        (button) => {
            button.addEventListener(
                "click",
                closeModal,
            );
        },
    );

    modal.addEventListener(
        "click",
        (event) => {
            if (event.target !== modal) {
                return;
            }

            const panel = modal.querySelector(
                ".modal-panel",
            );

            if (!(panel instanceof HTMLElement)) {
                closeModal();
                return;
            }

            const bounds = panel.getBoundingClientRect();

            const clickedInsidePanel = (
                event.clientX >= bounds.left
                && event.clientX <= bounds.right
                && event.clientY >= bounds.top
                && event.clientY <= bounds.bottom
            );

            if (!clickedInsidePanel) {
                closeModal();
            }
        },
    );

    modal.addEventListener(
        "close",
        restoreFocus,
    );

    if (
        messageInput
        instanceof HTMLTextAreaElement
    ) {
        messageInput.addEventListener(
            "input",
            updateCharacterCount,
        );
    }

    if (form instanceof HTMLFormElement) {
        form.addEventListener(
            "submit",
            () => {
                updatePageUrl();
            },
        );
    }

    updateCharacterCount();
}
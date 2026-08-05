document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseTaskFilters();
    },
);


function initialiseTaskFilters() {
    document
        .querySelectorAll(
            "[data-task-filter-panel]",
        )
        .forEach(
            (panel) => {
                initialiseTaskFilterPanel(
                    panel,
                );
            },
        );

    document
        .querySelectorAll(
            "[data-task-filters]",
        )
        .forEach(
            (form) => {
                initialiseTaskFilterForm(
                    form,
                );
            },
        );
}


function initialiseTaskFilterPanel(panel) {
    if (!(panel instanceof HTMLDetailsElement)) {
        return;
    }

    panel.addEventListener(
        "toggle",
        () => {
            panel.dataset.expanded = (
                panel.open
                    ? "true"
                    : "false"
            );
        },
    );

    panel.dataset.expanded = (
        panel.open
            ? "true"
            : "false"
    );
}


function initialiseTaskFilterForm(form) {
    if (!(form instanceof HTMLFormElement)) {
        return;
    }

    const resetButton = form.querySelector(
        "[data-reset-filters]",
    );

    if (resetButton instanceof HTMLElement) {
        resetButton.addEventListener(
            "click",
            () => {
                const clearUrl = (
                    resetButton.dataset.clearUrl
                );

                if (clearUrl) {
                    window.location.assign(
                        clearUrl,
                    );

                    return;
                }

                form.reset();
                form.requestSubmit();
            },
        );
    }

    form.addEventListener(
        "submit",
        () => {
            normaliseTaskFilterValues(
                form,
            );
        },
    );
}


function normaliseTaskFilterValues(form) {
    form
        .querySelectorAll(
            "input[type='search'], input[type='text']",
        )
        .forEach(
            (field) => {
                if (!(field instanceof HTMLInputElement)) {
                    return;
                }

                field.value = field.value.trim();
            },
        );
}
document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseTaskFilters();
    },
);

function initialiseTaskFilters() {
    const form = document.querySelector(
        "[data-task-filters]",
    );

    if (!form) {
        return;
    }

    form
        .querySelectorAll(
            "select,input[type='search'],input[type='checkbox']",
        )
        .forEach(
            (field) => {
                field.addEventListener(
                    "change",
                    () => {
                        form.submit();
                    },
                );
            },
        );

    const resetButton =
        form.querySelector(
            "[data-reset-filters]",
        );

    if (!resetButton) {
        return;
    }

    resetButton.addEventListener(
        "click",
        () => {
            form.reset();
            form.submit();
        },
    );
}
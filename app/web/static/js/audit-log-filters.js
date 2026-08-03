document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseAuditLogFilters();
    },
);

function initialiseAuditLogFilters() {
    document
        .querySelectorAll("[data-audit-log-filters]")
        .forEach(
            (form) => {
                initialiseAuditDateValidation(
                    form,
                );

                initialiseAuditPageSizeFilter(
                    form,
                );

                initialiseAuditEntityFilters(
                    form,
                );

                initialiseAuditFilterReset(
                    form,
                );
            },
        );
}

function initialiseAuditDateValidation(form) {
    const fromInput = form.querySelector(
        "[name='created_from']",
    );

    const toInput = form.querySelector(
        "[name='created_to']",
    );

    if (
        !fromInput
        || !toInput
    ) {
        return;
    }

    const validateDateRange = () => {
        /*
         * Clear the previous custom error before checking the current values.
         */
        toInput.setCustomValidity(
            "",
        );

        if (
            !fromInput.value
            || !toInput.value
        ) {
            return;
        }

        if (
            toInput.value
            < fromInput.value
        ) {
            toInput.setCustomValidity(
                "The end date must be on or after the start date.",
            );
        }
    };

    fromInput.addEventListener(
        "change",
        validateDateRange,
    );

    toInput.addEventListener(
        "change",
        validateDateRange,
    );

    form.addEventListener(
        "submit",
        validateDateRange,
    );

    validateDateRange();
}

function initialiseAuditPageSizeFilter(form) {
    const pageSizeSelect = form.querySelector(
        "[name='page_size']",
    );

    if (!pageSizeSelect) {
        return;
    }

    pageSizeSelect.addEventListener(
        "change",
        () => {
            /*
             * Changing the number of results should return to the first page.
             */
            const pageInput = form.querySelector(
                "[name='page']",
            );

            if (pageInput) {
                pageInput.value = "1";
            }

            submitAuditFilterForm(
                form,
            );
        },
    );
}

function initialiseAuditEntityFilters(form) {
    const entityTypeSelect = form.querySelector(
        "[name='entity_type']",
    );

    const entityIdInput = form.querySelector(
        "[name='entity_id']",
    );

    if (
        !entityTypeSelect
        || !entityIdInput
    ) {
        return;
    }

    const updateEntityIdDescription = () => {
        const selectedEntityType =
            entityTypeSelect.value.trim();

        if (selectedEntityType) {
            entityIdInput.setAttribute(
                "aria-label",
                `${selectedEntityType} entity ID`,
            );

            entityIdInput.placeholder = (
                `${selectedEntityType} ID`
            );

            return;
        }

        entityIdInput.setAttribute(
            "aria-label",
            "Entity ID",
        );

        entityIdInput.placeholder = "Entity ID";
    };

    entityTypeSelect.addEventListener(
        "change",
        updateEntityIdDescription,
    );

    updateEntityIdDescription();
}

function initialiseAuditFilterReset(form) {
    const resetButton = form.querySelector(
        "[data-filter-reset]",
    );

    if (!resetButton) {
        return;
    }

    resetButton.addEventListener(
        "click",
        (event) => {
            const targetUrl =
                resetButton.dataset.filterReset;

            if (!targetUrl) {
                return;
            }

            event.preventDefault();

            window.location.assign(
                targetUrl,
            );
        },
    );
}

function submitAuditFilterForm(form) {
    if (
        typeof form.requestSubmit
        === "function"
    ) {
        form.requestSubmit();

        return;
    }

    form.submit();
}
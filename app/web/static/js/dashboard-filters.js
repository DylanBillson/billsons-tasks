document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseDashboardFilters();
    },
);

function initialiseDashboardFilters() {
    document
        .querySelectorAll("[data-dashboard-filters]")
        .forEach(
            (form) => {
                initialiseDashboardCompanyFilter(
                    form,
                );

                initialiseDashboardPageSizeFilter(
                    form,
                );

                initialiseDashboardFilterReset(
                    form,
                );
            },
        );
}

function initialiseDashboardCompanyFilter(form) {
    const companySelect = form.querySelector(
        "[name='company_id']",
    );

    const sectionSelect = form.querySelector(
        "[name='section_id']",
    );

    if (
        !companySelect
        || !sectionSelect
    ) {
        return;
    }

    const updateSectionOptions = () => {
        const selectedCompanyId =
            companySelect.value;

        let selectedSectionIsAvailable = false;

        sectionSelect
            .querySelectorAll("option")
            .forEach(
                (option) => {
                    const optionCompanyId =
                        option.dataset.companyId;

                    /*
                     * Keep the unfiltered "All Sections" option available.
                     */
                    if (!optionCompanyId) {
                        option.hidden = false;
                        option.disabled = false;

                        return;
                    }

                    const isAvailable = (
                        !selectedCompanyId
                        || optionCompanyId
                        === selectedCompanyId
                    );

                    option.hidden = !isAvailable;
                    option.disabled = !isAvailable;

                    if (
                        isAvailable
                        && option.selected
                    ) {
                        selectedSectionIsAvailable = true;
                    }
                },
            );

        if (
            sectionSelect.value
            && !selectedSectionIsAvailable
        ) {
            sectionSelect.value = "";
        }
    };

    updateSectionOptions();

    companySelect.addEventListener(
        "change",
        updateSectionOptions,
    );
}

function initialiseDashboardPageSizeFilter(form) {
    const pageSizeSelect = form.querySelector(
        "[name='page_size'][data-auto-submit]",
    );

    if (!pageSizeSelect) {
        return;
    }

    pageSizeSelect.addEventListener(
        "change",
        () => {
            submitFilterForm(
                form,
            );
        },
    );
}

function initialiseDashboardFilterReset(form) {
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

function submitFilterForm(form) {
    /*
     * requestSubmit() follows normal form validation and submit-event
     * behaviour. Fall back to submit() for older browsers.
     */
    if (
        typeof form.requestSubmit
        === "function"
    ) {
        form.requestSubmit();

        return;
    }

    form.submit();
}
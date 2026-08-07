document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseLiveUpdates();
    },
);


/*
 * -------------------------------------------------------------------------
 * Initialisation
 * -------------------------------------------------------------------------
 */


function initialiseLiveUpdates() {
    const configuration =
        getLiveUpdateConfiguration();

    if (!configuration.enabled) {
        return;
    }

    const roots = getLiveUpdateRoots();

    roots.forEach(
        (root) => {
            initialiseLiveUpdateRoot(
                root,
                configuration,
            );
        },
    );
}


function getLiveUpdateConfiguration() {
    const configured =
        window.billsonsLiveUpdates
        || {};

    const intervalSeconds =
        parsePositiveNumber(
            configured.pollIntervalSeconds,
            5,
        );

    return {
        enabled: configured.enabled !== false,
        pollIntervalMilliseconds: (
            intervalSeconds
            * 1000
        ),
    };
}


function getLiveUpdateRoots() {
    return Array.from(
        document.querySelectorAll(
            (
                "[data-task-board]"
                + ", [data-task-detail]"
            ),
        ),
    );
}


function initialiseLiveUpdateRoot(
    root,
    configuration,
) {
    if (
        !(
            root
            instanceof HTMLElement
        )
    ) {
        return;
    }

    const revision =
        getRootRevision(
            root,
        );

    const updateUrl =
        root.dataset.liveUpdateUrl;

    if (
        !revision
        || !updateUrl
    ) {
        return;
    }

    const state = {
        root,
        updateUrl,
        revision,
        requestInProgress: false,
        updatePending: false,
        stopped: false,
        timerId: null,
        pollIntervalMilliseconds: (
            configuration.pollIntervalMilliseconds
        ),
    };

    root.__billsonsLiveUpdateState =
        state;

    ensureLiveUpdateStatus(
        root,
    );

    scheduleNextPoll(
        state,
    );
}


/*
 * -------------------------------------------------------------------------
 * Polling
 * -------------------------------------------------------------------------
 */


function scheduleNextPoll(
    state,
) {
    if (
        state.stopped
        || state.timerId !== null
    ) {
        return;
    }

    state.timerId = window.setTimeout(
        async () => {
            state.timerId = null;

            await pollForLiveUpdates(
                state,
            );

            scheduleNextPoll(
                state,
            );
        },
        state.pollIntervalMilliseconds,
    );
}


async function pollForLiveUpdates(
    state,
) {
    if (
        state.stopped
        || state.requestInProgress
        || document.hidden
        || shouldPauseAutomaticRefresh(
            state.root,
        )
    ) {
        return;
    }

    state.requestInProgress = true;

    try {
        const payload =
            await requestRevision(
                state.updateUrl,
                state.revision,
            );

        if (
            payload
            && Number.isFinite(
                payload.poll_interval_seconds,
            )
            && payload.poll_interval_seconds > 0
        ) {
            state.pollIntervalMilliseconds = (
                payload.poll_interval_seconds
                * 1000
            );
        }

        if (!payload.changed) {
            setLiveUpdateStatus(
                state.root,
                "idle",
                "",
            );

            return;
        }

        state.revision =
            payload.revision;

        setRootRevision(
            state.root,
            payload.revision,
        );

        if (
            shouldDeferRefresh(
                state.root,
            )
        ) {
            state.updatePending = true;

            setLiveUpdateStatus(
                state.root,
                "conflict",
                (
                    "Updates are available. "
                    + "Refresh when you are ready."
                ),
                {
                    showAction: true,
                },
            );

            return;
        }

        reloadForLiveUpdate(
            state.root,
        );

    } catch (error) {
        handlePollingError(
            state,
            error,
        );

    } finally {
        state.requestInProgress = false;
    }
}


async function requestRevision(
    updateUrl,
    knownRevision,
) {
    const url = new URL(
        updateUrl,
        window.location.origin,
    );

    if (knownRevision) {
        url.searchParams.set(
            "known_revision",
            knownRevision,
        );
    }

    const response = await fetch(
        url.toString(),
        {
            method: "GET",
            credentials: "same-origin",
            headers: {
                "Accept": "application/json",
                "Cache-Control": "no-cache",
            },
            cache: "no-store",
        },
    );

    let payload = null;

    try {
        payload = await response.json();

    } catch {
        payload = null;
    }

    if (response.ok) {
        return payload;
    }

    const error = new Error(
        (
            payload
            && typeof payload.detail
            === "string"
        )
            ? payload.detail
            : (
                "Live-update request failed "
                + `with status ${response.status}.`
            ),
    );

    error.status = response.status;

    if (
        payload
        && typeof payload.code
        === "string"
    ) {
        error.code = payload.code;
    }

    throw error;
}


/*
 * -------------------------------------------------------------------------
 * Refresh coordination
 * -------------------------------------------------------------------------
 */


function shouldPauseAutomaticRefresh(
    root,
) {
    return (
        root.matches(
            "[aria-busy='true']",
        )
        || root.classList.contains(
            "is-dragging-task",
        )
        || root.classList.contains(
            "is-dragging-list",
        )
        || root.classList.contains(
            "is-preparing-task-drag",
        )
        || root.classList.contains(
            "is-preparing-list-drag",
        )
        || root.classList.contains(
            "is-saving-order",
        )
    );
}


function shouldDeferRefresh(
    root,
) {
    if (
        shouldPauseAutomaticRefresh(
            root,
        )
    ) {
        return true;
    }

    const activeElement =
        document.activeElement;

    if (
        activeElement
        instanceof HTMLInputElement
        || activeElement
        instanceof HTMLTextAreaElement
        || activeElement
        instanceof HTMLSelectElement
    ) {
        return root.contains(
            activeElement,
        );
    }

    return Boolean(
        root.querySelector(
            "[data-submission-pending='true']",
        ),
    );
}


function reloadForLiveUpdate(
    root,
) {
    setLiveUpdateStatus(
        root,
        "updating",
        "New updates found. Refreshing…",
    );

    root.setAttribute(
        "aria-busy",
        "true",
    );

    window.setTimeout(
        () => {
            window.location.reload();
        },
        150,
    );
}


function handlePollingError(
    state,
    error,
) {
    if (
        error
        && (
            error.status === 401
            || error.status === 404
        )
    ) {
        state.stopped = true;

        setLiveUpdateStatus(
            state.root,
            "error",
            (
                "Live updates stopped because "
                + "access is no longer available."
            ),
            {
                showAction: true,
            },
        );

        return;
    }

    if (
        error
        && error.code
        === "live_updates_disabled"
    ) {
        state.stopped = true;

        setLiveUpdateStatus(
            state.root,
            "idle",
            "",
        );

        return;
    }

    setLiveUpdateStatus(
        state.root,
        navigator.onLine
            ? "error"
            : "offline",
        navigator.onLine
            ? "Unable to check for updates."
            : "Offline. Live updates are paused.",
        {
            showAction: true,
        },
    );
}


/*
 * -------------------------------------------------------------------------
 * Public coordination API
 * -------------------------------------------------------------------------
 */


async function refreshRevision(
    root,
) {
    if (
        !(
            root
            instanceof HTMLElement
        )
    ) {
        return null;
    }

    const state =
        root.__billsonsLiveUpdateState;

    const updateUrl = (
        state
        ? state.updateUrl
        : root.dataset.liveUpdateUrl
    );

    if (!updateUrl) {
        return null;
    }

    const payload =
        await requestRevision(
            updateUrl,
            null,
        );

    if (
        !payload
        || typeof payload.revision
        !== "string"
    ) {
        return null;
    }

    setRootRevision(
        root,
        payload.revision,
    );

    if (state) {
        state.revision =
            payload.revision;

        state.updatePending =
            false;
    }

    setLiveUpdateStatus(
        root,
        "idle",
        "",
    );

    return payload.revision;
}


function markConflict(
    root,
    message,
    currentRevision,
) {
    if (
        !(
            root
            instanceof HTMLElement
        )
    ) {
        window.location.reload();
        return;
    }

    const state =
        root.__billsonsLiveUpdateState;

    if (
        typeof currentRevision
        === "string"
        && currentRevision
    ) {
        setRootRevision(
            root,
            currentRevision,
        );

        if (state) {
            state.revision =
                currentRevision;
        }
    }

    if (state) {
        state.stopped = true;
        state.updatePending = true;
    }

    setLiveUpdateStatus(
        root,
        "conflict",
        (
            message
            || (
                "This page changed in another browser. "
                + "Refreshing…"
            )
        ),
    );

    root.setAttribute(
        "aria-busy",
        "true",
    );

    window.setTimeout(
        () => {
            window.location.reload();
        },
        650,
    );
}


window.BillsonsLiveUpdates = {
    refreshRevision,
    markConflict,
};


/*
 * -------------------------------------------------------------------------
 * Status display
 * -------------------------------------------------------------------------
 */


function ensureLiveUpdateStatus(
    root,
) {
    let status = root.querySelector(
        "[data-live-update-status]",
    );

    if (status) {
        initialiseStatusAction(
            status,
        );

        return status;
    }

    status = document.createElement(
        "div",
    );

    status.className =
        "live-update-status";

    status.dataset.liveUpdateStatus = "";
    status.dataset.state = "idle";

    status.setAttribute(
        "role",
        "status",
    );

    status.setAttribute(
        "aria-live",
        "polite",
    );

    status.setAttribute(
        "aria-atomic",
        "true",
    );

    status.hidden = true;

    const indicator =
        document.createElement(
            "span",
        );

    indicator.className =
        "live-update-status-indicator";

    indicator.setAttribute(
        "aria-hidden",
        "true",
    );

    const message =
        document.createElement(
            "span",
        );

    message.className =
        "live-update-status-message";

    message.dataset.liveUpdateStatusMessage = "";

    const action =
        document.createElement(
            "button",
        );

    action.type = "button";

    action.className =
        "live-update-status-action";

    action.dataset.liveUpdateRetry = "";

    action.textContent = "Refresh";
    action.hidden = true;

    status.append(
        indicator,
        message,
        action,
    );

    root.prepend(
        status,
    );

    initialiseStatusAction(
        status,
    );

    return status;
}


function initialiseStatusAction(
    status,
) {
    const action = status.querySelector(
        "[data-live-update-retry]",
    );

    if (
        !(
            action
            instanceof HTMLButtonElement
        )
        || action.dataset.liveUpdateBound
        === "true"
    ) {
        return;
    }

    action.dataset.liveUpdateBound =
        "true";

    action.addEventListener(
        "click",
        () => {
            window.location.reload();
        },
    );
}


function setLiveUpdateStatus(
    root,
    state,
    message,
    {
        showAction = false,
    } = {},
) {
    const status =
        ensureLiveUpdateStatus(
            root,
        );

    status.dataset.state =
        state;

    const messageElement =
        status.querySelector(
            "[data-live-update-status-message]",
        );

    if (messageElement) {
        messageElement.textContent =
            message;
    }

    const action =
        status.querySelector(
            "[data-live-update-retry]",
        );

    if (action) {
        action.hidden =
            !showAction;
    }

    status.hidden = (
        state === "idle"
        || !message
    );
}


/*
 * -------------------------------------------------------------------------
 * Revision helpers
 * -------------------------------------------------------------------------
 */


function getRootRevision(
    root,
) {
    if (
        root.matches(
            "[data-task-board]",
        )
    ) {
        return (
            root.dataset.sectionRevision
            || null
        );
    }

    return (
        root.dataset.taskRevision
        || null
    );
}


function setRootRevision(
    root,
    revision,
) {
    if (
        root.matches(
            "[data-task-board]",
        )
    ) {
        root.dataset.sectionRevision =
            revision;

        return;
    }

    root.dataset.taskRevision =
        revision;
}


function parsePositiveNumber(
    value,
    fallback,
) {
    const parsed =
        Number(
            value,
        );

    if (
        !Number.isFinite(
            parsed,
        )
        || parsed <= 0
    ) {
        return fallback;
    }

    return parsed;
}
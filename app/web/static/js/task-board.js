document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseTaskBoards();
        initialiseTaskMoveButtons();
    },
);


/*
 * -------------------------------------------------------------------------
 * Task boards
 * -------------------------------------------------------------------------
 */


function initialiseTaskBoards() {
    document
        .querySelectorAll(
            "[data-task-board]",
        )
        .forEach(
            (board) => {
                initialiseTaskBoard(
                    board,
                );
            },
        );
}


function initialiseTaskBoard(
    board,
) {
    if (
        !(
            board
            instanceof HTMLElement
        )
    ) {
        return;
    }

    synchroniseTaskListEmptyStates(
        board,
    );

    updateTaskListCounts(
        board,
    );

    if (
        board.dataset.dragEnabled
        !== "true"
    ) {
        return;
    }

    if (
        typeof window.Sortable
        !== "function"
    ) {
        console.error(
            "SortableJS is not available. "
            + "Task-board dragging has not been initialised.",
        );

        board.dataset.sortableUnavailable =
            "true";

        return;
    }

    const boardState = {
        requestInProgress: false,
        taskSortables: [],
        listSortable: null,
    };

    initialiseTaskSortables(
        board,
        boardState,
    );

    if (
        board.dataset.listDragEnabled
        === "true"
    ) {
        initialiseListSortable(
            board,
            boardState,
        );
    }

    board.dataset.sortableInitialised =
        "true";
}


/*
 * -------------------------------------------------------------------------
 * Task dragging
 * -------------------------------------------------------------------------
 */


function initialiseTaskSortables(
    board,
    boardState,
) {
    getTaskListContainers(
        board,
    ).forEach(
        (taskList) => {
            const sortable = new window.Sortable(
                taskList,
                {
                    group: {
                        name: (
                            "section-task-board-"
                            + (
                                board.dataset.sectionId
                                || "default"
                            )
                        ),
                        pull: true,
                        put: true,
                    },

                    animation: 180,

                    easing: (
                        "cubic-bezier("
                        + "0.2, 0, 0, 1"
                        + ")"
                    ),

                    handle: (
                        "[data-task-drag-handle]"
                    ),

                    draggable: (
                        "[data-task-card]"
                    ),

                    direction: "vertical",

                    ghostClass: (
                        "task-card-sortable-ghost"
                    ),

                    chosenClass: (
                        "task-card-sortable-chosen"
                    ),

                    dragClass: (
                        "task-card-sortable-drag"
                    ),

                    fallbackClass: (
                        "task-card-sortable-fallback"
                    ),

                    fallbackOnBody: true,

                    fallbackTolerance: 3,

                    forceFallback: false,

                    swapThreshold: 0.65,

                    invertSwap: false,

                    emptyInsertThreshold: 36,

                    scroll: true,

                    bubbleScroll: true,

                    scrollSensitivity: 100,

                    scrollSpeed: 14,

                    delay: 0,

                    delayOnTouchOnly: true,

                    touchStartThreshold: 4,

                    disabled: false,

                    onChoose: (
                        event,
                    ) => {
                        handleTaskChoose(
                            board,
                            event,
                        );
                    },

                    onStart: (
                        event,
                    ) => {
                        handleTaskDragStart(
                            board,
                            event,
                        );
                    },

                    onMove: (
                        event,
                    ) => {
                        return handleTaskDragMove(
                            board,
                            event,
                        );
                    },

                    onEnd: async (
                        event,
                    ) => {
                        await handleTaskDragEnd(
                            board,
                            boardState,
                            event,
                        );
                    },
                },
            );

            boardState.taskSortables.push(
                sortable,
            );
        },
    );
}


function handleTaskChoose(
    board,
    event,
) {
    if (
        !(
            event.item
            instanceof HTMLElement
        )
    ) {
        return;
    }

    event.item.classList.add(
        "is-sortable-chosen",
    );

    board.classList.add(
        "is-preparing-task-drag",
    );
}


function handleTaskDragStart(
    board,
    event,
) {
    board.classList.remove(
        "is-preparing-task-drag",
    );

    board.classList.add(
        "is-dragging-task",
    );

    removeTaskListEmptyStates(
        board,
    );

    const sourceList =
        getTaskListContainer(
            event.from,
        );

    if (sourceList) {
        sourceList.classList.add(
            "is-task-drag-source",
        );
    }

    if (
        event.item
        instanceof HTMLElement
    ) {
        event.item.classList.add(
            "is-dragging",
        );
    }
}


function handleTaskDragMove(
    board,
    event,
) {
    clearTaskDropTargets(
        board,
    );

    const destinationList =
        getTaskListContainer(
            event.to,
        );

    if (destinationList) {
        destinationList.classList.add(
            "is-task-drop-target",
        );
    }

    if (
        event.related
        instanceof HTMLElement
        && event.related.matches(
            "[data-task-card]",
        )
    ) {
        event.related.classList.add(
            event.willInsertAfter
                ? "is-insertion-after"
                : "is-insertion-before",
        );
    }

    return true;
}


async function handleTaskDragEnd(
    board,
    boardState,
    event,
) {
    clearTaskDragClasses(
        board,
    );

    if (
        event.item
        instanceof HTMLElement
    ) {
        event.item.classList.remove(
            "is-sortable-chosen",
            "is-dragging",
        );
    }

    const destinationList =
        getTaskListContainer(
            event.to,
        );

    if (
        destinationList
        && event.item
        instanceof HTMLElement
    ) {
        updateTaskCardListData(
            event.item,
            destinationList,
        );
    }

    updateTaskSortPositionData(
        board,
    );

    synchroniseTaskListEmptyStates(
        board,
    );

    updateTaskListCounts(
        board,
    );

    const orderChanged = (
        event.from !== event.to
        || event.oldIndex !== event.newIndex
    );

    if (!orderChanged) {
        return;
    }

    if (
        boardState.requestInProgress
    ) {
        window.location.reload();
        return;
    }

    boardState.requestInProgress =
        true;

    setBoardSavingState(
        board,
        boardState,
        true,
    );

    try {
        await persistTaskOrder(
            board,
        );

        board.dispatchEvent(
            new CustomEvent(
                "taskboard:tasks-reordered",
                {
                    detail: {
                        taskId: getNumericDataValue(
                            event.item,
                            "taskId",
                        ),
                        oldIndex: event.oldIndex,
                        newIndex: event.newIndex,
                        oldListId: getNumericDataValue(
                            event.from,
                            "listId",
                        ),
                        newListId: getNumericDataValue(
                            event.to,
                            "listId",
                        ),
                    },
                },
            ),
        );

    } catch (error) {
        console.error(
            "Unable to save task order.",
            error,
        );

        window.alert(
            getErrorMessage(
                error,
                (
                    "The task could not be moved. "
                    + "The board will be reloaded."
                ),
            ),
        );

        window.location.reload();

    } finally {
        boardState.requestInProgress =
            false;

        setBoardSavingState(
            board,
            boardState,
            false,
        );
    }
}


/*
 * -------------------------------------------------------------------------
 * List dragging
 * -------------------------------------------------------------------------
 */


function initialiseListSortable(
    board,
    boardState,
) {
    boardState.listSortable =
        new window.Sortable(
            board,
            {
                animation: 200,

                easing: (
                    "cubic-bezier("
                    + "0.2, 0, 0, 1"
                    + ")"
                ),

                handle: (
                    "[data-list-drag-handle]"
                ),

                draggable: (
                    "[data-task-list]"
                ),

                direction: "horizontal",

                ghostClass: (
                    "task-list-sortable-ghost"
                ),

                chosenClass: (
                    "task-list-sortable-chosen"
                ),

                dragClass: (
                    "task-list-sortable-drag"
                ),

                fallbackClass: (
                    "task-list-sortable-fallback"
                ),

                fallbackOnBody: true,

                fallbackTolerance: 3,

                forceFallback: false,

                swapThreshold: 0.55,

                invertSwap: false,

                scroll: true,

                bubbleScroll: true,

                scrollSensitivity: 120,

                scrollSpeed: 16,

                delay: 0,

                delayOnTouchOnly: true,

                touchStartThreshold: 4,

                disabled: false,

                onChoose: (
                    event,
                ) => {
                    handleListChoose(
                        board,
                        event,
                    );
                },

                onStart: (
                    event,
                ) => {
                    handleListDragStart(
                        board,
                        event,
                    );
                },

                onMove: (
                    event,
                ) => {
                    return handleListDragMove(
                        board,
                        event,
                    );
                },

                onEnd: async (
                    event,
                ) => {
                    await handleListDragEnd(
                        board,
                        boardState,
                        event,
                    );
                },
            },
        );
}


function handleListChoose(
    board,
    event,
) {
    if (
        event.item
        instanceof HTMLElement
    ) {
        event.item.classList.add(
            "is-sortable-chosen",
        );
    }

    board.classList.add(
        "is-preparing-list-drag",
    );
}


function handleListDragStart(
    board,
    event,
) {
    board.classList.remove(
        "is-preparing-list-drag",
    );

    board.classList.add(
        "is-dragging-list",
    );

    if (
        event.item
        instanceof HTMLElement
    ) {
        event.item.classList.add(
            "is-dragging",
        );
    }
}


function handleListDragMove(
    board,
    event,
) {
    clearListDropTargets(
        board,
    );

    if (
        event.related
        instanceof HTMLElement
        && event.related.matches(
            "[data-task-list]",
        )
    ) {
        event.related.classList.add(
            "is-list-drop-target",
        );

        event.related.classList.add(
            event.willInsertAfter
                ? "is-insertion-after"
                : "is-insertion-before",
        );
    }

    return true;
}


async function handleListDragEnd(
    board,
    boardState,
    event,
) {
    clearListDragClasses(
        board,
    );

    if (
        event.item
        instanceof HTMLElement
    ) {
        event.item.classList.remove(
            "is-sortable-chosen",
            "is-dragging",
        );
    }

    updateListSortPositionData(
        board,
    );

    const orderChanged = (
        event.oldIndex !== event.newIndex
    );

    if (!orderChanged) {
        return;
    }

    if (
        boardState.requestInProgress
    ) {
        window.location.reload();
        return;
    }

    boardState.requestInProgress =
        true;

    setBoardSavingState(
        board,
        boardState,
        true,
    );

    try {
        await persistListOrder(
            board,
        );

        board.dispatchEvent(
            new CustomEvent(
                "taskboard:lists-reordered",
                {
                    detail: {
                        listId: getNumericDataValue(
                            event.item,
                            "listId",
                        ),
                        oldIndex: event.oldIndex,
                        newIndex: event.newIndex,
                    },
                },
            ),
        );

    } catch (error) {
        console.error(
            "Unable to save list order.",
            error,
        );

        window.alert(
            getErrorMessage(
                error,
                (
                    "The list order could not be saved. "
                    + "The board will be reloaded."
                ),
            ),
        );

        window.location.reload();

    } finally {
        boardState.requestInProgress =
            false;

        setBoardSavingState(
            board,
            boardState,
            false,
        );
    }
}


/*
 * -------------------------------------------------------------------------
 * Persistence
 * -------------------------------------------------------------------------
 */


async function persistTaskOrder(
    board,
) {
    const reorderUrl =
        board.dataset.reorderUrl;

    const csrfToken =
        board.dataset.csrfToken;

    if (
        !reorderUrl
        || !csrfToken
    ) {
        throw new Error(
            "The task reorder configuration is incomplete.",
        );
    }

    const items = [];

    getTaskLists(
        board,
    ).forEach(
        (list) => {
            const listId =
                getNumericDataValue(
                    list,
                    "listId",
                );

            if (listId === null) {
                throw new Error(
                    "A task list has an invalid identifier.",
                );
            }

            const taskList =
                getTaskListContainer(
                    list,
                );

            if (!taskList) {
                throw new Error(
                    "A task list container is missing.",
                );
            }

            getTaskCards(
                taskList,
            ).forEach(
                (
                    card,
                    index,
                ) => {
                    const taskId =
                        getNumericDataValue(
                            card,
                            "taskId",
                        );

                    if (taskId === null) {
                        throw new Error(
                            "A task has an invalid identifier.",
                        );
                    }

                    items.push(
                        {
                            task_id: taskId,
                            section_list_id:
                                listId,
                            sort_position:
                                (index + 1) * 1000,
                        },
                    );
                },
            );
        },
    );

    const response = await fetch(
        reorderUrl,
        {
            method: "POST",

            credentials: "same-origin",

            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },

            body: JSON.stringify(
                {
                    items,
                },
            ),
        },
    );

    await requireSuccessfulResponse(
        response,
    );
}


async function persistListOrder(
    board,
) {
    const reorderUrl =
        board.dataset.listReorderUrl;

    const csrfToken =
        board.dataset.csrfToken;

    if (
        !reorderUrl
        || !csrfToken
    ) {
        throw new Error(
            "The list reorder configuration is incomplete.",
        );
    }

    const items = getTaskLists(
        board,
    ).map(
        (
            list,
            index,
        ) => {
            const listId =
                getNumericDataValue(
                    list,
                    "listId",
                );

            if (listId === null) {
                throw new Error(
                    "A task list has an invalid identifier.",
                );
            }

            return {
                list_id: listId,
                sort_position:
                    (index + 1) * 1000,
            };
        },
    );

    const response = await fetch(
        reorderUrl,
        {
            method: "POST",

            credentials: "same-origin",

            headers: {
                "Accept": "application/json",
                "Content-Type": "application/json",
                "X-CSRF-Token": csrfToken,
            },

            body: JSON.stringify(
                {
                    items,
                },
            ),
        },
    );

    await requireSuccessfulResponse(
        response,
    );
}


/*
 * -------------------------------------------------------------------------
 * Board state
 * -------------------------------------------------------------------------
 */


function setBoardSavingState(
    board,
    boardState,
    isSaving,
) {
    board.classList.toggle(
        "is-saving-order",
        isSaving,
    );

    board.setAttribute(
        "aria-busy",
        isSaving
            ? "true"
            : "false",
    );

    boardState.taskSortables.forEach(
        (sortable) => {
            sortable.option(
                "disabled",
                isSaving,
            );
        },
    );

    if (boardState.listSortable) {
        boardState.listSortable.option(
            "disabled",
            isSaving,
        );
    }
}


function updateTaskCardListData(
    card,
    taskList,
) {
    const listId =
        getNumericDataValue(
            taskList,
            "listId",
        );

    if (listId === null) {
        return;
    }

    card.dataset.listId =
        String(
            listId,
        );
}


function updateTaskSortPositionData(
    board,
) {
    getTaskLists(
        board,
    ).forEach(
        (list) => {
            const listId =
                getNumericDataValue(
                    list,
                    "listId",
                );

            const taskList =
                getTaskListContainer(
                    list,
                );

            if (
                listId === null
                || !taskList
            ) {
                return;
            }

            getTaskCards(
                taskList,
            ).forEach(
                (
                    card,
                    index,
                ) => {
                    card.dataset.sortPosition =
                        String(
                            (index + 1)
                            * 1000,
                        );

                    card.dataset.listId =
                        String(
                            listId,
                        );
                },
            );
        },
    );
}


function updateListSortPositionData(
    board,
) {
    getTaskLists(
        board,
    ).forEach(
        (
            list,
            index,
        ) => {
            list.dataset.sortPosition =
                String(
                    (index + 1)
                    * 1000,
                );
        },
    );
}


function updateTaskListCounts(
    board,
) {
    getTaskLists(
        board,
    ).forEach(
        (list) => {
            const taskList =
                getTaskListContainer(
                    list,
                );

            if (!taskList) {
                return;
            }

            const count =
                getTaskCards(
                    taskList,
                ).length;

            const countElement =
                list.querySelector(
                    "[data-task-list-count]",
                );

            if (!countElement) {
                return;
            }

            countElement.textContent =
                String(
                    count,
                );

            countElement.setAttribute(
                "aria-label",
                `${count} tasks`,
            );
        },
    );
}


/*
 * -------------------------------------------------------------------------
 * Empty-list states
 * -------------------------------------------------------------------------
 */


function synchroniseTaskListEmptyStates(
    board,
) {
    getTaskListContainers(
        board,
    ).forEach(
        (taskList) => {
            const taskCount =
                getTaskCards(
                    taskList,
                ).length;

            const emptyState =
                taskList.querySelector(
                    ":scope > [data-task-list-empty]",
                );

            if (taskCount > 0) {
                if (emptyState) {
                    emptyState.remove();
                }

                return;
            }

            if (emptyState) {
                return;
            }

            taskList.appendChild(
                createTaskListEmptyState(),
            );
        },
    );
}


function removeTaskListEmptyStates(
    board,
) {
    board
        .querySelectorAll(
            "[data-task-list-empty]",
        )
        .forEach(
            (emptyState) => {
                emptyState.remove();
            },
        );
}


function createTaskListEmptyState() {
    const emptyState =
        document.createElement(
            "div",
        );

    emptyState.className = (
        "empty-state "
        + "empty-state-compact "
        + "task-list-empty"
    );

    emptyState.dataset.taskListEmpty = "";

    const message =
        document.createElement(
            "p",
        );

    message.textContent =
        "No tasks in this list.";

    emptyState.appendChild(
        message,
    );

    return emptyState;
}


/*
 * -------------------------------------------------------------------------
 * Drag classes and insertion indicators
 * -------------------------------------------------------------------------
 */


function clearTaskDragClasses(
    board,
) {
    board.classList.remove(
        "is-preparing-task-drag",
        "is-dragging-task",
    );

    clearTaskDropTargets(
        board,
    );

    board
        .querySelectorAll(
            ".is-task-drag-source",
        )
        .forEach(
            (element) => {
                element.classList.remove(
                    "is-task-drag-source",
                );
            },
        );
}


function clearTaskDropTargets(
    board,
) {
    board
        .querySelectorAll(
            (
                ".is-task-drop-target, "
                + ".is-insertion-before, "
                + ".is-insertion-after"
            ),
        )
        .forEach(
            (element) => {
                element.classList.remove(
                    "is-task-drop-target",
                    "is-insertion-before",
                    "is-insertion-after",
                );
            },
        );
}


function clearListDragClasses(
    board,
) {
    board.classList.remove(
        "is-preparing-list-drag",
        "is-dragging-list",
    );

    clearListDropTargets(
        board,
    );
}


function clearListDropTargets(
    board,
) {
    board
        .querySelectorAll(
            (
                ".is-list-drop-target, "
                + ".is-insertion-before, "
                + ".is-insertion-after"
            ),
        )
        .forEach(
            (element) => {
                element.classList.remove(
                    "is-list-drop-target",
                    "is-insertion-before",
                    "is-insertion-after",
                );
            },
        );
}


/*
 * -------------------------------------------------------------------------
 * DOM helpers
 * -------------------------------------------------------------------------
 */


function getTaskLists(
    board,
) {
    return Array.from(
        board.querySelectorAll(
            ":scope > [data-task-list]",
        ),
    );
}


function getTaskListContainers(
    board,
) {
    return Array.from(
        board.querySelectorAll(
            (
                "[data-task-list-container], "
                + "[data-task-list-items]"
            ),
        ),
    );
}


function getTaskListContainer(
    element,
) {
    if (
        !(
            element
            instanceof Element
        )
    ) {
        return null;
    }

    if (
        element.matches(
            (
                "[data-task-list-container], "
                + "[data-task-list-items]"
            ),
        )
    ) {
        return element;
    }

    return element.querySelector(
        (
            "[data-task-list-container], "
            + "[data-task-list-items]"
        ),
    );
}


function getTaskCards(
    taskList,
) {
    return Array.from(
        taskList.querySelectorAll(
            ":scope > [data-task-card]",
        ),
    );
}


function getNumericDataValue(
    element,
    key,
) {
    if (
        !(
            element
            instanceof HTMLElement
        )
    ) {
        return null;
    }

    const value =
        element.dataset[key];

    if (!value) {
        return null;
    }

    const numericValue =
        Number(
            value,
        );

    if (
        !Number.isInteger(
            numericValue,
        )
        || numericValue < 1
    ) {
        return null;
    }

    return numericValue;
}


/*
 * -------------------------------------------------------------------------
 * Response handling
 * -------------------------------------------------------------------------
 */


async function requireSuccessfulResponse(
    response,
) {
    if (response.ok) {
        return;
    }

    let detail = (
        "Request failed with status "
        + `${response.status}.`
    );

    try {
        const payload =
            await response.json();

        if (
            payload
            && typeof payload.detail
            === "string"
        ) {
            detail =
                payload.detail;
        }

    } catch {
        /*
         * Preserve the generic HTTP error when the response is not JSON.
         */
    }

    throw new Error(
        detail,
    );
}


function getErrorMessage(
    error,
    fallback,
) {
    if (
        error instanceof Error
        && error.message
    ) {
        return error.message;
    }

    return fallback;
}


/*
 * -------------------------------------------------------------------------
 * Task-detail move control
 * -------------------------------------------------------------------------
 */


function initialiseTaskMoveButtons() {
    document
        .querySelectorAll(
            "[data-task-move-button]",
        )
        .forEach(
            (button) => {
                button.addEventListener(
                    "click",
                    async () => {
                        await moveTaskFromDetailPage(
                            button,
                        );
                    },
                );
            },
        );
}


async function moveTaskFromDetailPage(
    button,
) {
    const select =
        document.querySelector(
            "[data-task-move-list]",
        );

    if (
        !(
            select
            instanceof HTMLSelectElement
        )
    ) {
        return;
    }

    const moveUrl =
        button.dataset.moveUrl;

    const csrfToken =
        button.dataset.csrfToken;

    if (
        !moveUrl
        || !csrfToken
        || !select.value
    ) {
        return;
    }

    button.disabled = true;

    button.setAttribute(
        "aria-disabled",
        "true",
    );

    try {
        const response = await fetch(
            moveUrl,
            {
                method: "POST",

                credentials: "same-origin",

                headers: {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                    "X-CSRF-Token": csrfToken,
                },

                body: JSON.stringify(
                    {
                        destination_list_id:
                            Number(
                                select.value,
                            ),

                        sort_position:
                            1000,
                    },
                ),
            },
        );

        await requireSuccessfulResponse(
            response,
        );

        window.location.reload();

    } catch (error) {
        console.error(
            "Unable to move task.",
            error,
        );

        window.alert(
            getErrorMessage(
                error,
                "The task could not be moved.",
            ),
        );

    } finally {
        button.disabled = false;

        button.removeAttribute(
            "aria-disabled",
        );
    }
}
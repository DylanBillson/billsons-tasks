document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseTaskBoards();
        initialiseTaskMoveButtons();
    },
);


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


function initialiseTaskBoard(board) {
    if (!(board instanceof HTMLElement)) {
        return;
    }

    if (board.dataset.dragEnabled !== "true") {
        return;
    }

    initialiseTaskDragging(
        board,
    );

    if (
        board.dataset.listDragEnabled
        === "true"
    ) {
        initialiseListDragging(
            board,
        );
    }

    synchroniseTaskListEmptyStates(
        board,
    );

    updateTaskListCounts(
        board,
    );
}


function initialiseTaskDragging(board) {
    let draggedCard = null;
    let originalState = null;
    let requestInProgress = false;

    board
        .querySelectorAll(
            "[data-task-card][draggable='true']",
        )
        .forEach(
            (card) => {
                card.addEventListener(
                    "dragstart",
                    (event) => {
                        event.stopPropagation();

                        if (
                            requestInProgress
                            || !isTaskDragStartAllowed(
                                event,
                                card,
                            )
                        ) {
                            event.preventDefault();
                            return;
                        }

                        const taskList = card.closest(
                            "[data-task-list-items]",
                        );

                        if (!(taskList instanceof HTMLElement)) {
                            event.preventDefault();
                            return;
                        }

                        draggedCard = card;

                        originalState = {
                            taskList,
                            nextSibling:
                                card.nextElementSibling,
                            listId:
                                card.dataset.listId,
                            sortPosition:
                                card.dataset.sortPosition,
                        };

                        card.classList.add(
                            "is-dragging",
                        );

                        board.classList.add(
                            "is-dragging-task",
                        );

                        if (event.dataTransfer) {
                            event.dataTransfer.effectAllowed =
                                "move";

                            event.dataTransfer.setData(
                                "text/plain",
                                card.dataset.taskId || "",
                            );
                        }
                    },
                );

                card.addEventListener(
                    "dragend",
                    (event) => {
                        event.stopPropagation();

                        card.classList.remove(
                            "is-dragging",
                        );

                        board.classList.remove(
                            "is-dragging-task",
                        );

                        clearTaskDropIndicators(
                            board,
                        );

                        synchroniseTaskListEmptyStates(
                            board,
                        );

                        updateTaskListCounts(
                            board,
                        );

                        draggedCard = null;
                        originalState = null;
                    },
                );
            },
        );

    board
        .querySelectorAll(
            "[data-task-list-items]",
        )
        .forEach(
            (taskList) => {
                taskList.addEventListener(
                    "dragenter",
                    (event) => {
                        if (!draggedCard) {
                            return;
                        }

                        event.preventDefault();

                        taskList.classList.add(
                            "is-task-drop-target",
                        );
                    },
                );

                taskList.addEventListener(
                    "dragover",
                    (event) => {
                        if (!draggedCard) {
                            return;
                        }

                        event.preventDefault();

                        if (event.dataTransfer) {
                            event.dataTransfer.dropEffect =
                                "move";
                        }

                        taskList.classList.add(
                            "is-task-drop-target",
                        );

                        removeEmptyState(
                            taskList,
                        );

                        const insertBefore =
                            getTaskInsertionPoint(
                                taskList,
                                event.clientY,
                                draggedCard,
                            );

                        if (insertBefore) {
                            taskList.insertBefore(
                                draggedCard,
                                insertBefore,
                            );
                        } else {
                            taskList.appendChild(
                                draggedCard,
                            );
                        }

                        updateTaskCardListData(
                            draggedCard,
                            taskList,
                        );

                        updateTaskListCounts(
                            board,
                        );

                        synchroniseTaskListEmptyStates(
                            board,
                            {
                                excludeTaskList:
                                    taskList,
                            },
                        );
                    },
                );

                taskList.addEventListener(
                    "dragleave",
                    (event) => {
                        if (
                            event.relatedTarget instanceof Node
                            && taskList.contains(
                                event.relatedTarget,
                            )
                        ) {
                            return;
                        }

                        taskList.classList.remove(
                            "is-task-drop-target",
                        );
                    },
                );

                taskList.addEventListener(
                    "drop",
                    async (event) => {
                        if (
                            !draggedCard
                            || requestInProgress
                        ) {
                            return;
                        }

                        event.preventDefault();
                        event.stopPropagation();

                        requestInProgress = true;

                        clearTaskDropIndicators(
                            board,
                        );

                        updateTaskCardListData(
                            draggedCard,
                            taskList,
                        );

                        updateTaskListCounts(
                            board,
                        );

                        synchroniseTaskListEmptyStates(
                            board,
                        );

                        try {
                            await persistTaskOrder(
                                board,
                            );

                            updateTaskSortPositionData(
                                board,
                            );

                            board.dispatchEvent(
                                new CustomEvent(
                                    "taskboard:tasks-reordered",
                                ),
                            );

                        } catch (error) {
                            console.error(
                                "Unable to save task order.",
                                error,
                            );

                            restoreTaskPosition(
                                draggedCard,
                                originalState,
                            );

                            updateTaskSortPositionData(
                                board,
                            );

                            synchroniseTaskListEmptyStates(
                                board,
                            );

                            updateTaskListCounts(
                                board,
                            );

                            window.alert(
                                error.message
                                || (
                                    "The task could not be moved. "
                                    + "Its previous position has "
                                    + "been restored."
                                ),
                            );

                        } finally {
                            requestInProgress = false;
                        }
                    },
                );
            },
        );
}


function isTaskDragStartAllowed(
    event,
    card,
) {
    const target = event.target;

    if (!(target instanceof Element)) {
        return true;
    }

    if (
        target.closest(
            "a, button, input, select, textarea",
        )
    ) {
        return false;
    }

    const handle = card.querySelector(
        "[data-task-drag-handle]",
    );

    if (!handle) {
        return true;
    }

    return (
        target === handle
        || handle.contains(
            target,
        )
    );
}


function restoreTaskPosition(
    card,
    originalState,
) {
    if (
        !(card instanceof HTMLElement)
        || !originalState
        || !(
            originalState.taskList
            instanceof HTMLElement
        )
    ) {
        return;
    }

    removeEmptyState(
        originalState.taskList,
    );

    if (
        originalState.nextSibling
        && originalState.nextSibling.parentElement
            === originalState.taskList
    ) {
        originalState.taskList.insertBefore(
            card,
            originalState.nextSibling,
        );
    } else {
        originalState.taskList.appendChild(
            card,
        );
    }

    card.dataset.listId = (
        originalState.listId || ""
    );

    card.dataset.sortPosition = (
        originalState.sortPosition || ""
    );
}


function initialiseListDragging(board) {
    let draggedList = null;
    let originalState = null;
    let requestInProgress = false;

    board
        .querySelectorAll(
            ":scope > [data-task-list][draggable='true']",
        )
        .forEach(
            (list) => {
                list.addEventListener(
                    "dragstart",
                    (event) => {
                        const target = event.target;

                        if (
                            target instanceof Element
                            && target.closest(
                                "[data-task-card]",
                            )
                        ) {
                            return;
                        }

                        const handle = (
                            target instanceof Element
                                ? target.closest(
                                    "[data-list-drag-handle]",
                                )
                                : null
                        );

                        if (
                            !handle
                            || requestInProgress
                        ) {
                            event.preventDefault();
                            return;
                        }

                        draggedList = list;

                        originalState = {
                            nextSibling:
                                list.nextElementSibling,
                            sortPosition:
                                list.dataset.sortPosition,
                        };

                        list.classList.add(
                            "is-dragging",
                        );

                        board.classList.add(
                            "is-dragging-list",
                        );

                        if (event.dataTransfer) {
                            event.dataTransfer.effectAllowed =
                                "move";

                            event.dataTransfer.setData(
                                "text/plain",
                                list.dataset.listId || "",
                            );
                        }
                    },
                );

                list.addEventListener(
                    "dragend",
                    () => {
                        list.classList.remove(
                            "is-dragging",
                        );

                        board.classList.remove(
                            "is-dragging-list",
                        );

                        draggedList = null;
                        originalState = null;
                    },
                );
            },
        );

    board.addEventListener(
        "dragover",
        (event) => {
            if (!draggedList) {
                return;
            }

            event.preventDefault();

            if (event.dataTransfer) {
                event.dataTransfer.dropEffect =
                    "move";
            }

            const insertBefore =
                getListInsertionPoint(
                    board,
                    event.clientX,
                    draggedList,
                );

            if (insertBefore) {
                board.insertBefore(
                    draggedList,
                    insertBefore,
                );
            } else {
                board.appendChild(
                    draggedList,
                );
            }
        },
    );

    board.addEventListener(
        "drop",
        async (event) => {
            if (
                !draggedList
                || requestInProgress
            ) {
                return;
            }

            event.preventDefault();
            event.stopPropagation();

            requestInProgress = true;

            try {
                await persistListOrder(
                    board,
                );

                updateListSortPositionData(
                    board,
                );

                board.dispatchEvent(
                    new CustomEvent(
                        "taskboard:lists-reordered",
                    ),
                );

            } catch (error) {
                console.error(
                    "Unable to save list order.",
                    error,
                );

                restoreListPosition(
                    board,
                    draggedList,
                    originalState,
                );

                updateListSortPositionData(
                    board,
                );

                window.alert(
                    error.message
                    || (
                        "The list order could not be saved. "
                        + "Its previous position has been restored."
                    ),
                );

            } finally {
                requestInProgress = false;
            }
        },
    );
}


function restoreListPosition(
    board,
    list,
    originalState,
) {
    if (
        !(list instanceof HTMLElement)
        || !originalState
    ) {
        return;
    }

    if (
        originalState.nextSibling
        && originalState.nextSibling.parentElement
            === board
    ) {
        board.insertBefore(
            list,
            originalState.nextSibling,
        );
    } else {
        board.appendChild(
            list,
        );
    }

    list.dataset.sortPosition = (
        originalState.sortPosition || ""
    );
}


function getTaskInsertionPoint(
    taskList,
    pointerY,
    draggedCard,
) {
    const cards = [
        ...taskList.querySelectorAll(
            ":scope > [data-task-card]:not(.is-dragging)",
        ),
    ];

    let closest = {
        offset: Number.NEGATIVE_INFINITY,
        element: null,
    };

    cards.forEach(
        (card) => {
            if (card === draggedCard) {
                return;
            }

            const rectangle =
                card.getBoundingClientRect();

            const offset = (
                pointerY
                - rectangle.top
                - rectangle.height / 2
            );

            if (
                offset < 0
                && offset > closest.offset
            ) {
                closest = {
                    offset,
                    element: card,
                };
            }
        },
    );

    return closest.element;
}


function getListInsertionPoint(
    board,
    pointerX,
    draggedList,
) {
    const lists = [
        ...board.querySelectorAll(
            ":scope > [data-task-list]:not(.is-dragging)",
        ),
    ];

    let closest = {
        offset: Number.NEGATIVE_INFINITY,
        element: null,
    };

    lists.forEach(
        (list) => {
            if (list === draggedList) {
                return;
            }

            const rectangle =
                list.getBoundingClientRect();

            const offset = (
                pointerX
                - rectangle.left
                - rectangle.width / 2
            );

            if (
                offset < 0
                && offset > closest.offset
            ) {
                closest = {
                    offset,
                    element: list,
                };
            }
        },
    );

    return closest.element;
}


async function persistTaskOrder(board) {
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

    board
        .querySelectorAll(
            ":scope > [data-task-list]",
        )
        .forEach(
            (list) => {
                const listId = Number(
                    list.dataset.listId,
                );

                list
                    .querySelectorAll(
                        "[data-task-list-items] "
                        + "> [data-task-card]",
                    )
                    .forEach(
                        (card, index) => {
                            items.push(
                                {
                                    task_id: Number(
                                        card.dataset.taskId,
                                    ),
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


async function persistListOrder(board) {
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

    const items = [
        ...board.querySelectorAll(
            ":scope > [data-task-list]",
        ),
    ].map(
        (list, index) => ({
            list_id: Number(
                list.dataset.listId,
            ),
            sort_position:
                (index + 1) * 1000,
        }),
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


function updateTaskCardListData(
    card,
    taskList,
) {
    card.dataset.listId = (
        taskList.dataset.listId || ""
    );
}


function updateTaskSortPositionData(board) {
    board
        .querySelectorAll(
            ":scope > [data-task-list]",
        )
        .forEach(
            (list) => {
                list
                    .querySelectorAll(
                        "[data-task-list-items] "
                        + "> [data-task-card]",
                    )
                    .forEach(
                        (card, index) => {
                            card.dataset.sortPosition =
                                String(
                                    (index + 1)
                                    * 1000,
                                );

                            card.dataset.listId = (
                                list.dataset.listId || ""
                            );
                        },
                    );
            },
        );
}


function updateListSortPositionData(board) {
    board
        .querySelectorAll(
            ":scope > [data-task-list]",
        )
        .forEach(
            (list, index) => {
                list.dataset.sortPosition =
                    String(
                        (index + 1) * 1000,
                    );
            },
        );
}


function updateTaskListCounts(board) {
    board
        .querySelectorAll(
            ":scope > [data-task-list]",
        )
        .forEach(
            (list) => {
                const count = (
                    list.querySelectorAll(
                        "[data-task-list-items] "
                        + "> [data-task-card]",
                    ).length
                );

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


function synchroniseTaskListEmptyStates(
    board,
    {
        excludeTaskList = null,
    } = {},
) {
    board
        .querySelectorAll(
            "[data-task-list-items]",
        )
        .forEach(
            (taskList) => {
                if (
                    taskList === excludeTaskList
                ) {
                    return;
                }

                const taskCount = (
                    taskList.querySelectorAll(
                        ":scope > [data-task-card]",
                    ).length
                );

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


function removeEmptyState(taskList) {
    const emptyState =
        taskList.querySelector(
            ":scope > [data-task-list-empty]",
        );

    if (emptyState) {
        emptyState.remove();
    }
}


function clearTaskDropIndicators(board) {
    board
        .querySelectorAll(
            ".is-task-drop-target",
        )
        .forEach(
            (element) => {
                element.classList.remove(
                    "is-task-drop-target",
                );
            },
        );
}


async function requireSuccessfulResponse(
    response,
) {
    if (response.ok) {
        return;
    }

    let detail = (
        `Request failed with status `
        + `${response.status}.`
    );

    try {
        const payload =
            await response.json();

        if (payload.detail) {
            detail = payload.detail;
        }
    } catch {
        // Preserve the generic response message.
    }

    throw new Error(
        detail,
    );
}


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


async function moveTaskFromDetailPage(button) {
    const select = document.querySelector(
        "[data-task-move-list]",
    );

    if (!(select instanceof HTMLSelectElement)) {
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
                        sort_position: 1000,
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
            error.message
            || "The task could not be moved.",
        );

    } finally {
        button.disabled = false;
    }
}
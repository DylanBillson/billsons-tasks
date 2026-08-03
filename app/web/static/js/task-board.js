document.addEventListener(
    "DOMContentLoaded",
    () => {
        initialiseTaskBoards();
        initialiseTaskMoveButtons();
    },
);


function initialiseTaskBoards() {
    document
        .querySelectorAll("[data-task-board]")
        .forEach(
            (board) => {
                initialiseTaskBoard(board);
            },
        );
}


function initialiseTaskBoard(board) {
    if (board.dataset.dragEnabled !== "true") {
        return;
    }

    initialiseTaskDragging(board);
    initialiseListDragging(board);
}


function initialiseTaskDragging(board) {
    let draggedCard = null;
    let originalList = null;
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

                        if (requestInProgress) {
                            event.preventDefault();
                            return;
                        }

                        draggedCard = card;

                        originalList = card.closest(
                            "[data-task-list-items]",
                        );

                        card.classList.add(
                            "is-dragging",
                        );

                        board.classList.add(
                            "is-dragging-task",
                        );

                        event.dataTransfer.effectAllowed =
                            "move";

                        event.dataTransfer.setData(
                            "text/plain",
                            card.dataset.taskId,
                        );
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
                        originalList = null;
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

                        event.dataTransfer.dropEffect =
                            "move";

                        taskList.classList.add(
                            "is-task-drop-target",
                        );

                        const insertBefore =
                            getTaskInsertionPoint(
                                taskList,
                                event.clientY,
                                draggedCard,
                            );

                        removeEmptyState(
                            taskList,
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
                            event.relatedTarget
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

                            updateTaskListCounts(
                                board,
                            );

                            synchroniseTaskListEmptyStates(
                                board,
                            );
                        } catch (error) {
                            console.error(
                                "Unable to save task order.",
                                error,
                            );

                            if (
                                originalList
                                && draggedCard
                            ) {
                                removeEmptyState(
                                    originalList,
                                );

                                originalList.appendChild(
                                    draggedCard,
                                );
                            }

                            updateTaskListCounts(
                                board,
                            );

                            synchroniseTaskListEmptyStates(
                                board,
                            );

                            window.alert(
                                "The task could not be moved. "
                                + "The board will be reloaded.",
                            );

                            window.location.reload();
                        } finally {
                            requestInProgress = false;
                        }
                    },
                );
            },
        );
}


function initialiseListDragging(board) {
    let draggedList = null;
    let requestInProgress = false;

    board
        .querySelectorAll(
            "[data-task-list][draggable='true']",
        )
        .forEach(
            (list) => {
                list.addEventListener(
                    "dragstart",
                    (event) => {
                        if (
                            event.target.closest(
                                "[data-task-card]",
                            )
                        ) {
                            return;
                        }

                        const handle =
                            event.target.closest(
                                "[data-list-drag-handle]",
                            );

                        if (
                            !handle
                            || requestInProgress
                        ) {
                            event.preventDefault();
                            return;
                        }

                        draggedList = list;

                        list.classList.add(
                            "is-dragging",
                        );

                        board.classList.add(
                            "is-dragging-list",
                        );

                        event.dataTransfer.effectAllowed =
                            "move";

                        event.dataTransfer.setData(
                            "text/plain",
                            list.dataset.listId,
                        );
                    },
                );

                list.addEventListener(
                    "dragend",
                    (event) => {
                        if (
                            event.target.closest(
                                "[data-task-card]",
                            )
                        ) {
                            return;
                        }

                        list.classList.remove(
                            "is-dragging",
                        );

                        board.classList.remove(
                            "is-dragging-list",
                        );

                        draggedList = null;
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

            event.dataTransfer.dropEffect =
                "move";

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

            requestInProgress = true;

            try {
                await persistListOrder(
                    board,
                );

                updateListSortPositionData(
                    board,
                );
            } catch (error) {
                console.error(
                    "Unable to save list order.",
                    error,
                );

                window.alert(
                    "The list order could not be saved. "
                    + "The board will be reloaded.",
                );

                window.location.reload();
            } finally {
                requestInProgress = false;
            }
        },
    );
}


function getTaskInsertionPoint(
    taskList,
    pointerY,
    draggedCard,
) {
    const cards = [
        ...taskList.querySelectorAll(
            "[data-task-card]:not(.is-dragging)",
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

            const offset =
                pointerY
                - rectangle.top
                - rectangle.height / 2;

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
            ":scope > [data-task-list]"
            + ":not(.is-dragging)",
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

            const offset =
                pointerX
                - rectangle.left
                - rectangle.width / 2;

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
            "[data-task-list]",
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
                            items.push({
                                task_id: Number(
                                    card.dataset.taskId,
                                ),
                                section_list_id:
                                    listId,
                                sort_position:
                                    (index + 1) * 1000,
                            });
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
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
                "X-CSRF-Token":
                    csrfToken,
            },
            body: JSON.stringify({
                items,
            }),
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
                "Accept":
                    "application/json",
                "Content-Type":
                    "application/json",
                "X-CSRF-Token":
                    csrfToken,
            },
            body: JSON.stringify({
                items,
            }),
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
    card.dataset.listId =
        taskList.dataset.listId;
}


function updateTaskSortPositionData(board) {
    board
        .querySelectorAll(
            "[data-task-list]",
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

                            card.dataset.listId =
                                list.dataset.listId;
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
            "[data-task-list]",
        )
        .forEach(
            (list) => {
                const count =
                    list.querySelectorAll(
                        "[data-task-list-items] "
                        + "> [data-task-card]",
                    ).length;

                const countElement =
                    list.querySelector(
                        "[data-task-list-count]",
                    );

                if (!countElement) {
                    return;
                }

                countElement.textContent =
                    String(count);

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
                    taskList
                    === excludeTaskList
                ) {
                    return;
                }

                const taskCount =
                    taskList.querySelectorAll(
                        ":scope > [data-task-card]",
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


function createTaskListEmptyState() {
    const emptyState =
        document.createElement(
            "div",
        );

    emptyState.className =
        "empty-state "
        + "empty-state-compact "
        + "task-list-empty";

    emptyState.dataset.taskListEmpty =
        "";

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

    let detail =
        `Request failed with status `
        + `${response.status}.`;

    try {
        const payload =
            await response.json();

        if (payload.detail) {
            detail = payload.detail;
        }
    } catch {
        // Keep the generic error message.
    }

    throw new Error(detail);
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

    if (!select) {
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
                    "Accept":
                        "application/json",
                    "Content-Type":
                        "application/json",
                    "X-CSRF-Token":
                        csrfToken,
                },
                body: JSON.stringify({
                    destination_list_id:
                        Number(
                            select.value,
                        ),
                    sort_position: 1000,
                }),
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
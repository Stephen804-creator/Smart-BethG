"use strict";


/*
 * Smart BethG
 * Application Frontend Controller
 *
 * Responsibilities:
 * - Sidebar state
 * - Navigation state
 * - UI action dispatching
 * - Global search events
 * - Notification/settings events
 * - Assistant form protection
 *
 * This file does NOT:
 * - authenticate users
 * - authorise actions
 * - access database records
 * - store API keys
 * - make security decisions
 * - execute arbitrary commands
 * - control agents directly
 */


document.addEventListener("DOMContentLoaded", initializeApplication);


/**
 * Application bootstrap.
 */
function initializeApplication() {
    const app = document.querySelector(".app");

    if (!app) {
        return;
    }

    initializeSidebar(app);
    initializeNavigation();
    initializeActionDispatcher();
    initializeGlobalSearch();
    initializeTopbarActions();
    initializeAssistantForm();
}


/**
 * Initialise sidebar controls.
 */
function initializeSidebar(app) {
    const toggle = document.getElementById("sidebarToggle");

    if (!toggle) {
        return;
    }

    const isCollapsed = app.classList.contains("sidebar-collapsed");

    updateSidebarState(toggle, isCollapsed);


    toggle.addEventListener("click", () => {
        const collapsed = app.classList.toggle("sidebar-collapsed");

        updateSidebarState(toggle, collapsed);
    });
}


/**
 * Keep sidebar accessibility state synchronized
 * with the visual state.
 */
function updateSidebarState(toggle, collapsed) {
    toggle.setAttribute(
        "aria-expanded",
        String(!collapsed)
    );

    toggle.setAttribute(
        "aria-label",
        collapsed
            ? "Expand sidebar"
            : "Collapse sidebar"
    );
}


/**
 * Highlight the current navigation item.
 */
function initializeNavigation() {
    const currentPath = normalizePath(
        window.location.pathname
    );


    const links = document.querySelectorAll(
        ".sidebar-navigation a[href]"
    );


    links.forEach((link) => {
        const href = link.getAttribute("href");

        if (!href || href === "#") {
            return;
        }


        try {
            const linkPath = normalizePath(
                new URL(
                    href,
                    window.location.origin
                ).pathname
            );


            const isCurrent =
                linkPath === currentPath;


            link.classList.toggle(
                "active",
                isCurrent
            );


            if (isCurrent) {
                link.setAttribute(
                    "aria-current",
                    "page"
                );
            } else {
                link.removeAttribute(
                    "aria-current"
                );
            }

        } catch {
            /*
             * Invalid navigation URLs should not
             * break the rest of the application.
             */
        }
    });
}


/**
 * Remove unnecessary trailing slashes
 * so navigation comparisons remain consistent.
 */
function normalizePath(path) {
    if (!path) {
        return "/";
    }

    const normalized = path.replace(
        /\/+$/,
        ""
    );

    return normalized || "/";
}


/**
 * Handle all elements using data-action.
 *
 * Event delegation means dynamically-created
 * buttons can also use the same mechanism.
 */
function initializeActionDispatcher() {
    document.addEventListener(
        "click",
        handleActionClick
    );
}


/**
 * Convert a clicked action button into
 * an application-level event.
 */
function handleActionClick(event) {
    const button = event.target.closest(
        "[data-action]"
    );

    if (!button) {
        return;
    }


    if (
        button.disabled ||
        button.getAttribute("aria-disabled") === "true"
    ) {
        return;
    }


    const action =
        button.dataset.action?.trim();


    if (!action) {
        return;
    }


    const missionId =
        button.dataset.missionId || null;


    const taskId =
        button.dataset.taskId || null;


    const detail = {
        action,
        missionId,
        taskId
    };


    document.dispatchEvent(
        new CustomEvent(
            "smartbethg:action",
            {
                detail
            }
        )
    );
}


/**
 * Initialise global search.
 */
function initializeGlobalSearch() {
    const form =
        document.getElementById(
            "globalSearchForm"
        );


    const input =
        document.getElementById(
            "globalSearch"
        );


    if (!form || !input) {
        return;
    }


    form.addEventListener(
        "submit",
        (event) => {
            event.preventDefault();


            const query =
                input.value.trim();


            if (!query) {
                input.focus();
                return;
            }


            document.dispatchEvent(
                new CustomEvent(
                    "smartbethg:search",
                    {
                        detail: {
                            query
                        }
                    }
                )
            );
        }
    );
}


/**
 * Initialise notification and settings
 * controls.
 */
function initializeTopbarActions() {
    const notificationsButton =
        document.getElementById(
            "notificationsButton"
        );


    const settingsButton =
        document.getElementById(
            "settingsButton"
        );


    if (notificationsButton) {
        notificationsButton.addEventListener(
            "click",
            () => {
                document.dispatchEvent(
                    new CustomEvent(
                        "smartbethg:notifications"
                    )
                );
            }
        );
    }


    if (settingsButton) {
        settingsButton.addEventListener(
            "click",
            () => {
                document.dispatchEvent(
                    new CustomEvent(
                        "smartbethg:settings"
                    )
                );
            }
        );
    }
}


/**
 * Protect the assistant form against:
 *
 * - empty whitespace-only messages
 * - accidental repeated submissions
 */
function initializeAssistantForm() {
    const form =
        document.getElementById(
            "assistantForm"
        );


    const input =
        document.getElementById(
            "assistantPrompt"
        );


    if (!form || !input) {
        return;
    }


    const submitButton =
        form.querySelector(
            'button[type="submit"]'
        );


    let submitting = false;


    form.addEventListener(
        "submit",
        (event) => {

            const message =
                input.value.trim();


            if (!message) {
                event.preventDefault();

                input.focus();

                return;
            }


            if (submitting) {
                event.preventDefault();

                return;
            }


            submitting = true;


            if (submitButton) {
                submitButton.disabled = true;

                submitButton.setAttribute(
                    "aria-busy",
                    "true"
                );


                const label =
                    submitButton.querySelector(
                        "span"
                    );


                if (label) {
                    label.textContent =
                        "Sending...";
                }
            }
        }
    );
}

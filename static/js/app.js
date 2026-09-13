"use strict";

/*
 * Smart BethG
 * Global Application Controller
 *
 * Responsibilities:
 * - Application bootstrap
 * - Sidebar state
 * - Navigation state
 * - Global action dispatch
 * - Global search
 * - Topbar events
 * - Assistant form protection
 *
 * This file does NOT:
 * - authenticate users
 * - authorise actions
 * - access databases
 * - store secrets
 * - execute commands
 * - control agents directly
 */

(function () {
    "use strict";

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

    function initializeSidebar(app) {
        const toggle = document.getElementById("sidebarToggle");

        if (!toggle) {
            return;
        }

        const collapsed =
            app.classList.contains("sidebar-collapsed");

        updateSidebarState(toggle, collapsed);

        toggle.addEventListener("click", () => {
            const isCollapsed =
                app.classList.toggle("sidebar-collapsed");

            updateSidebarState(toggle, isCollapsed);
        });
    }

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

    function initializeNavigation() {
        const currentPath =
            normalizePath(window.location.pathname);

        const links =
            document.querySelectorAll(
                ".sidebar-navigation a[href]"
            );

        links.forEach((link) => {
            const href =
                link.getAttribute("href");

            if (!href || href === "#") {
                return;
            }

            try {
                const linkPath =
                    normalizePath(
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
            } catch (error) {
                console.warn(
                    "Invalid navigation URL:",
                    href,
                    error
                );
            }
        });
    }

    function normalizePath(path) {
        if (!path) {
            return "/";
        }

        const normalized =
            path.replace(/\/+$/, "");

        return normalized || "/";
    }

    function initializeActionDispatcher() {
        document.addEventListener(
            "click",
            handleActionClick
        );
    }

    function handleActionClick(event) {
        const target =
            event.target.closest("[data-action]");

        if (!target) {
            return;
        }

        if (
            target.disabled ||
            target.getAttribute("aria-disabled") === "true"
        ) {
            return;
        }

        const action =
            target.dataset.action?.trim();

        if (!action) {
            return;
        }

        document.dispatchEvent(
            new CustomEvent(
                "smartbethg:action",
                {
                    detail: {
                        action,
                        missionId:
                            target.dataset.missionId || null,
                        taskId:
                            target.dataset.taskId || null
                    }
                }
            )
        );
    }

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

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeApplication
        );
    } else {
        initializeApplication();
    }

})();

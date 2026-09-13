/* =========================================================
   SMART BETHG
   Main Application JavaScript
   ========================================================= */

document.addEventListener("DOMContentLoaded", () => {

    const sideMenu =
        document.getElementById("sideMenu");

    const menuBackdrop =
        document.getElementById("menuBackdrop");

    const openMenuButton =
        document.getElementById("openMenuButton");

    const closeMenuButton =
        document.getElementById("closeMenuButton");

    const searchButton =
        document.getElementById("searchButton");

    const searchPanel =
        document.getElementById("searchPanel");

    const closeSearchButton =
        document.getElementById("closeSearchButton");

    const notificationButton =
        document.getElementById("notificationButton");

    const notificationPanel =
        document.getElementById("notificationPanel");

    const closeNotificationButton =
        document.getElementById(
            "closeNotificationButton"
        );

    const globalSearchInput =
        document.getElementById(
            "globalSearchInput"
        );


    /* =====================================================
       SIDE MENU
       ===================================================== */

    function openMenu() {

        if (!sideMenu) {
            return;
        }

        sideMenu.classList.add("open");

        menuBackdrop.classList.add(
            "visible"
        );

        sideMenu.setAttribute(
            "aria-hidden",
            "false"
        );
    }


    function closeMenu() {

        if (!sideMenu) {
            return;
        }

        sideMenu.classList.remove("open");

        menuBackdrop.classList.remove(
            "visible"
        );

        sideMenu.setAttribute(
            "aria-hidden",
            "true"
        );
    }


    if (openMenuButton) {
        openMenuButton.addEventListener(
            "click",
            openMenu
        );
    }


    if (closeMenuButton) {
        closeMenuButton.addEventListener(
            "click",
            closeMenu
        );
    }


    if (menuBackdrop) {
        menuBackdrop.addEventListener(
            "click",
            closeMenu
        );
    }


    /* =====================================================
       SEARCH PANEL
       ===================================================== */

    function openSearch() {

        closeMenu();
        closeNotifications();

        searchPanel.classList.add("open");

        searchPanel.setAttribute(
            "aria-hidden",
            "false"
        );

        setTimeout(() => {

            if (globalSearchInput) {
                globalSearchInput.focus();
            }

        }, 100);
    }


    function closeSearch() {

        searchPanel.classList.remove(
            "open"
        );

        searchPanel.setAttribute(
            "aria-hidden",
            "true"
        );
    }


    if (searchButton) {
        searchButton.addEventListener(
            "click",
            openSearch
        );
    }


    if (closeSearchButton) {
        closeSearchButton.addEventListener(
            "click",
            closeSearch
        );
    }


    /* =====================================================
       NOTIFICATIONS
       ===================================================== */

    function openNotifications() {

        closeMenu();
        closeSearch();

        notificationPanel.classList.add(
            "open"
        );

        notificationPanel.setAttribute(
            "aria-hidden",
            "false"
        );
    }


    function closeNotifications() {

        notificationPanel.classList.remove(
            "open"
        );

        notificationPanel.setAttribute(
            "aria-hidden",
            "true"
        );
    }


    if (notificationButton) {
        notificationButton.addEventListener(
            "click",
            () => {

                if (
                    notificationPanel.classList.contains(
                        "open"
                    )
                ) {
                    closeNotifications();
                } else {
                    openNotifications();
                }

            }
        );
    }


    if (closeNotificationButton) {
        closeNotificationButton.addEventListener(
            "click",
            closeNotifications
        );
    }


    /* =====================================================
       VIEW NAVIGATION
       ===================================================== */

    function showView(viewName) {

        const views =
            document.querySelectorAll(
                "[data-view-content]"
            );

        const menuItems =
            document.querySelectorAll(
                ".menu-item[data-view]"
            );


        let foundView = false;


        views.forEach((view) => {

            const matches =
                view.dataset.viewContent ===
                viewName;

            view.classList.toggle(
                "active",
                matches
            );

            if (matches) {
                foundView = true;
            }
        });


        if (!foundView) {

            console.warn(
                "Smart BethG view not found:",
                viewName
            );

            return;
        }


        menuItems.forEach((item) => {

            item.classList.toggle(
                "active",
                item.dataset.view ===
                viewName
            );

        });


        closeMenu();

        closeSearch();

        closeNotifications();

        window.scrollTo({
            top: 0,
            behavior: "smooth"
        });
    }


    document
        .querySelectorAll(
            ".menu-item[data-view]"
        )
        .forEach((item) => {

            item.addEventListener(
                "click",
                () => {

                    showView(
                        item.dataset.view
                    );

                }
            );

        });


    document
        .querySelectorAll(
            "[data-view-target]"
        )
        .forEach((button) => {

            button.addEventListener(
                "click",
                () => {

                    showView(
                        button.dataset.viewTarget
                    );

                }
            );

        });


    /* =====================================================
       SEARCH SUGGESTIONS
       ===================================================== */

    document
        .querySelectorAll(
            ".suggestion-item"
        )
        .forEach((item) => {

            item.addEventListener(
                "click",
                () => {

                    const command =
                        item.dataset.command;

                    if (!command) {
                        return;
                    }


                    closeSearch();


                    const commandInput =
                        document.getElementById(
                            "commandInput"
                        );


                    if (commandInput) {

                        commandInput.value =
                            command;

                        commandInput.focus();

                    }

                }
            );

        });


    /* =====================================================
       GLOBAL SEARCH KEY
       ===================================================== */

    document.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "/" &&
                document.activeElement.tagName !==
                    "INPUT" &&
                document.activeElement.tagName !==
                    "TEXTAREA"
            ) {

                event.preventDefault();

                openSearch();

            }


            if (event.key === "Escape") {

                closeMenu();
                closeSearch();
                closeNotifications();

            }

        }
    );


    /* =====================================================
       AUTO-RESIZE TEXTAREAS
       ===================================================== */

    document
        .querySelectorAll("textarea")
        .forEach((textarea) => {

            textarea.addEventListener(
                "input",
                () => {

                    textarea.style.height =
                        "auto";

                    textarea.style.height =
                        Math.min(
                            textarea.scrollHeight,
                            180
                        ) + "px";

                }
            );

        });


    /* =====================================================
       TEMPORARY COMMAND BEHAVIOUR
       ===================================================== */

    const commandForm =
        document.getElementById(
            "commandForm"
        );

    const commandInput =
        document.getElementById(
            "commandInput"
        );


    if (commandForm && commandInput) {

        commandForm.addEventListener(
            "submit",
            (event) => {

                event.preventDefault();

                const value =
                    commandInput.value.trim();


                if (!value) {
                    return;
                }


                /*
                 * We deliberately do NOT fake an AI answer here.
                 *
                 * The real backend agent runtime will be connected
                 * in the next backend chunk.
                 *
                 * For now, the command moves the user into Chat.
                 */

                commandInput.value = "";

                showView("chat");


                const chatInput =
                    document.getElementById(
                        "chatInput"
                    );


                if (chatInput) {

                    chatInput.value =
                        value;

                    chatInput.focus();

                }

            }
        );

    }


    /* =====================================================
       INITIAL STATE
       ===================================================== */

    showView("home");

});

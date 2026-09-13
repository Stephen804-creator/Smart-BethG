"use strict";

/*
 * Smart BethG
 * Chat Controller
 *
 * Responsibilities:
 * - Chat input
 * - Chat submission
 * - API communication
 * - Message rendering
 * - Chat loading state
 *
 * This file does NOT:
 * - authenticate users
 * - authorise requests
 * - store API keys
 * - execute commands
 * - make security decisions
 */

(function () {
    "use strict";

    function initializeChat() {
        const form =
            document.getElementById(
                "chatForm"
            );

        const input =
            document.getElementById(
                "chatPrompt"
            );

        const messages =
            document.getElementById(
                "chatMessages"
            );

        if (!form || !input || !messages) {
            return;
        }

        let submitting = false;

        form.addEventListener(
            "submit",
            async (event) => {
                event.preventDefault();

                if (submitting) {
                    return;
                }

                const prompt =
                    input.value.trim();

                if (!prompt) {
                    input.focus();
                    return;
                }

                submitting = true;

                appendMessage(
                    messages,
                    "user",
                    prompt
                );

                input.value = "";

                setChatBusy(
                    form,
                    input,
                    true
                );

                try {
                    const response =
                        await fetch(
                            "/api/chat",
                            {
                                method: "POST",

                                headers: {
                                    "Content-Type":
                                        "application/json",
                                    "Accept":
                                        "application/json"
                                },

                                body: JSON.stringify({
                                    message: prompt
                                })
                            }
                        );

                    if (!response.ok) {
                        throw new Error(
                            `Chat request failed with status ${response.status}`
                        );
                    }

                    const data =
                        await response.json();

                    const answer =
                        typeof data.answer === "string"
                            ? data.answer.trim()
                            : "";

                    appendMessage(
                        messages,
                        "assistant",
                        answer ||
                            "Smart BethG did not return a response."
                    );

                } catch (error) {
                    console.error(
                        "Smart BethG chat error:",
                        error
                    );

                    appendMessage(
                        messages,
                        "error",
                        "Smart BethG could not complete the request. Please try again."
                    );
                } finally {
                    submitting = false;

                    setChatBusy(
                        form,
                        input,
                        false
                    );

                    input.focus();
                }
            }
        );

        input.addEventListener(
            "keydown",
            (event) => {
                if (
                    event.key === "Enter" &&
                    !event.shiftKey
                ) {
                    event.preventDefault();

                    form.requestSubmit();
                }
            }
        );
    }

    function setChatBusy(
        form,
        input,
        busy
    ) {
        const button =
            form.querySelector(
                'button[type="submit"]'
            );

        input.disabled = busy;

        if (!button) {
            return;
        }

        button.disabled = busy;

        button.setAttribute(
            "aria-busy",
            String(busy)
        );

        const label =
            button.querySelector(
                "[data-submit-label]"
            );

        if (label) {
            label.textContent =
                busy
                    ? "Thinking..."
                    : "Send";
        }
    }

    function appendMessage(
        container,
        role,
        content
    ) {
        const article =
            document.createElement(
                "article"
            );

        article.className =
            `chat-message chat-message-${role}`;

        const meta =
            document.createElement(
                "div"
            );

        meta.className =
            "chat-message-meta";

        meta.textContent =
            getMessageLabel(role);

        const body =
            document.createElement(
                "div"
            );

        body.className =
            "chat-message-content";

        body.textContent =
            content;

        article.appendChild(meta);
        article.appendChild(body);

        container.appendChild(article);

        container.scrollTop =
            container.scrollHeight;
    }

    function getMessageLabel(role) {
        switch (role) {
            case "user":
                return "You";

            case "assistant":
                return "Smart BethG";

            case "error":
                return "System";

            default:
                return "Message";
        }
    }

    if (
        document.readyState === "loading"
    ) {
        document.addEventListener(
            "DOMContentLoaded",
            initializeChat
        );
    } else {
        initializeChat();
    }

})();

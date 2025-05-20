// Chat Actions: Clearing, Deleting, Title Editing, and related UI updates

// Depends on global: window.currentChatId, window.isNewChat, window.getCookie, window.appendSystemNotification (optional)
// Depends on DOM elements for chat list items if titles are updated there too.

document.addEventListener("DOMContentLoaded", function () {
    const clearChatButton = document.getElementById("clear-chat");
    const chatsListContainer = document.getElementById("chats-list"); // For attaching delete/edit to dynamic items

    // --- Clear Chat --- 
    if (clearChatButton) {
        clearChatButton.addEventListener("click", async () => {
            if (!window.currentChatId || window.currentChatId === "new") {
                if(window.appendSystemNotification) window.appendSystemNotification("No active chat to clear.", "info");
                else alert("No active chat to clear.");
                return;
            }
            if (!confirm("Are you sure you want to clear this conversation?")) return;
            
            try {
                const response = await fetch(`/chat/${window.currentChatId}/clear/`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": window.getCookie("csrftoken"),
                        "Content-Type": "application/json" 
                    }
                });
                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || "Failed to clear chat");
                }
                // Visually clear messages from the UI
                const messagesContainer = document.getElementById("chat-messages");
                if (messagesContainer) {
                    messagesContainer.innerHTML = `
                        <div class="flex flex-col items-center justify-center h-[calc(100vh-200px)]">
                            <img src="/static/images/logo.png" alt="Assistant icon" class="h-14 w-24">
                            <p class="text-gray-400 text-sm">How can I help you today?</p>
                        </div>
                    `;
                }
                if(window.appendSystemNotification) window.appendSystemNotification("Chat cleared successfully.", "info");

            } catch (error) {
                console.error("Error clearing chat:", error);
                if(window.appendSystemNotification) window.appendSystemNotification(`Error clearing chat: ${error.message}`, "error");
                else alert(`Error clearing chat: ${error.message}`);
            }
        });
    } else {
        console.warn("Clear chat button not found.");
    }

    // --- Delete Chat & Title Editing (Delegate for dynamic chats) --- 
    if (chatsListContainer) {
        chatsListContainer.addEventListener("click", async function(e) {
            // Delete Chat
            const deleteButton = e.target.closest(".delete-chat-btn");
            if (deleteButton) {
                e.preventDefault();
                e.stopPropagation();
                const chatId = deleteButton.dataset.chatId;
                if (!confirm("Are you sure you want to delete this chat?")) return;
                try {
                    const response = await fetch(`/chat/${chatId}/delete/`, {
                        method: "POST",
                        headers: {
                            "X-CSRFToken": window.getCookie("csrftoken"),
                            "Content-Type": "application/json"
                        }
                    });
                    if (!response.ok) {
                        const errorData = await response.json();
                        throw new Error(errorData.error || "Failed to delete chat");
                    }
                    const chatElement = deleteButton.closest("[data-chat-id]");
                    if (chatElement) chatElement.remove();
                    
                    if (chatId === window.currentChatId) {
                        window.location.href = "/chat/new/"; // Redirect to new chat if current one is deleted
                    }
                } catch (error) {
                    console.error("Error deleting chat:", error);
                    if(window.appendSystemNotification) window.appendSystemNotification(`Error deleting chat: ${error.message}`, "error");
                    else alert(`Error deleting chat: ${error.message}`);
                }
            }

            // Edit Chat Title (Initiate)
            const editButton = e.target.closest(".edit-title-btn"); // From sidebar
            if (editButton) {
                e.preventDefault();
                e.stopPropagation();
                const chatItemContainer = editButton.closest(".group"); // The whole chat item entry in sidebar
                const titleDisplayContainer = chatItemContainer.querySelector(".chat-title"); // The div/span showing title
                if (titleDisplayContainer) {
                    startEditingTitle(titleDisplayContainer, editButton.dataset.chatId);
                }
            }
        });
    }

    function startEditingTitle(titleDisplayContainer, chatId) {
        const currentTitle = titleDisplayContainer.textContent.trim();
        titleDisplayContainer.innerHTML = ''; // Clear current title text

        const input = document.createElement("input");
        input.type = "text";
        input.value = currentTitle;
        input.className = "w-full bg-gray-700/70 text-sm rounded px-2 py-1 text-gray-100 focus:outline-none focus:ring-1 focus:ring-gray-400";
        titleDisplayContainer.appendChild(input);
        input.focus();
        input.select();

        const finishEdit = async () => {
            await finishEditingTitle(titleDisplayContainer, input, currentTitle, chatId);
        };

        input.addEventListener("blur", finishEdit);
        input.addEventListener("keydown", (e) => {
            if (e.key === "Enter") {
                e.preventDefault();
                input.blur(); // Triggers finishEdit
            } else if (e.key === "Escape") {
                restoreTitleDisplay(titleDisplayContainer, currentTitle); // Restore original and remove input
            }
        });
    }
    window.startEditingTitle = startEditingTitle; // Expose if needed by dynamically added elements elsewhere

    async function finishEditingTitle(displayContainer, inputElement, originalTitle, chatId) {
        const newTitle = inputElement.value.trim();
        if (!newTitle || newTitle === originalTitle) {
            restoreTitleDisplay(displayContainer, originalTitle);
            return;
        }
        try {
            const response = await fetch(`/chat/${chatId}/update-title/`, {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": window.getCookie("csrftoken")
                },
                body: JSON.stringify({ title: newTitle })
            });
            if (!response.ok) {
                 const errorData = await response.json();
                throw new Error(errorData.error || "Failed to update title");
            }
            restoreTitleDisplay(displayContainer, newTitle);
            // If current chat title changed, update main UI elements
            if (chatId === window.currentChatId) {
                const pageTitleElement = document.querySelector("title"); // Browser tab title
                if (pageTitleElement) pageTitleElement.textContent = `${newTitle} - AI Chat Interface`;
                
                const mobileHeader = document.querySelector(".md\\:hidden h1"); // Title above messages on mobile
                if (mobileHeader) mobileHeader.textContent = newTitle;
            }
        } catch (error) {
            console.error("Error updating chat title:", error);
            restoreTitleDisplay(displayContainer, originalTitle);
            if(window.appendSystemNotification) window.appendSystemNotification(`Failed to update title: ${error.message}`, "error");
            else alert(`Failed to update title: ${error.message}`);
        }
    }

    function restoreTitleDisplay(container, title) {
        container.innerHTML = ''; // Clear input
        container.textContent = title; // Restore text
    }

    // --- UI Updates based on new/existing chat state ---
    // THIS FUNCTION IS NOW DEFERRED TO chat.js to avoid conflicts.
    // window.updateNewChatUI = function(isNew) { ... }; 
    
    // Initial call logic is also deferred or handled by chat.js directly setting window.isNewChat
    // and then the event listener below will pick up changes.

    // Listen for the custom event dispatched by chat.js
    document.addEventListener('chatStateChanged', function(event) {
        console.log("[chat_actions.js] Caught chatStateChanged event", event.detail);
        // Call the global updateNewChatUI function (expected to be defined in chat.js)
        if (typeof window.updateNewChatUI === 'function') {
            window.updateNewChatUI(event.detail.isNewChat);
        }
    });
}); 
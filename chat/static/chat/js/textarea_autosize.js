// Textarea auto-resize functionality for the main chat prompt

document.addEventListener("DOMContentLoaded", function () {
    const textarea = document.getElementById("prompt");

    if (!textarea) {
        console.warn("Main prompt textarea not found. Auto-resize will not work.");
        return;
    }

    // Auto-resize textarea function, now exposed globally for main prompt
    window.adjustMainTextareaHeight = function () {
        textarea.style.height = "auto"; // Reset height to shrink if text is deleted
        // Set height based on scrollHeight, capped at a max height (e.g., 200px)
        const maxHeight = 200;
        textarea.style.height = Math.min(textarea.scrollHeight, maxHeight) + "px";
    };

    textarea.addEventListener("input", window.adjustMainTextareaHeight);
    textarea.addEventListener("focus", window.adjustMainTextareaHeight); // Adjust on focus as well, e.g. if content loaded

    // Initial adjustment if textarea already has content on load
    if (textarea.value) {
        window.adjustMainTextareaHeight();
    }
});

// Note: The edit-message-textarea auto-resize is handled in message_edit.js
// This file is specifically for the main prompt textarea. 
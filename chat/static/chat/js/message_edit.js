document.addEventListener("DOMContentLoaded", () => {
	// Ensure chat.js has initialized window.currentChatId if this script relies on it at load time
	// However, for event listeners, it should be available by the time they trigger.
	initializeMessageEditing();
});

function initializeMessageEditing() {
	const messagesContainer = document.getElementById("chat-messages");
	if (!messagesContainer) {
		console.error("Chat messages container not found for edit functionality.");
		return;
	}

	messagesContainer.addEventListener("click", async (event) => {
		const target = event.target;
		const editButton = target.closest(".edit-message-btn");
		const saveButton = target.closest(".save-edit-btn");
		const cancelButton = target.closest(".cancel-edit-btn");

		if (editButton) {
			const messageId = editButton.dataset.messageId;
			const messageTextContainer = messagesContainer.querySelector(
				`.message-text-container[data-message-id="${messageId}"]`
			);
			if (messageTextContainer) {
				toggleEditUI(messageTextContainer, true);
			}
		} else if (saveButton) {
			const messageTextContainer = saveButton.closest(
				".message-text-container"
			);
			if (messageTextContainer) {
				const messageId = messageTextContainer.dataset.messageId;
				await handleSaveEdit(messageId, messageTextContainer);
			}
		} else if (cancelButton) {
			const messageTextContainer = cancelButton.closest(
				".message-text-container"
			);
			if (messageTextContainer) {
				toggleEditUI(messageTextContainer, false);
			}
		}
	});
}

function toggleEditUI(messageTextContainer, showEditUI) {
	const textElement = messageTextContainer.querySelector(
		".message-content-text"
	);
	const editControls = messageTextContainer.querySelector(".edit-controls");
	const textarea = editControls.querySelector(".edit-message-textarea");

	if (showEditUI) {
		textElement.classList.add("editing"); // Hides original text via CSS
		editControls.classList.remove("hidden");
		editControls.classList.add("active"); // Shows textarea/buttons via CSS
		textarea.value = textElement.textContent.trim(); // Populate textarea
		textarea.focus();
		adjustTextareaHeight(textarea); // Adjust height based on content
	} else {
		textElement.classList.remove("editing");
		editControls.classList.add("hidden");
		editControls.classList.remove("active");
	}
}

// Helper to adjust textarea height dynamically (similar to main chat input)
function adjustTextareaHeight(textareaElement) {
	textareaElement.style.height = "auto";
	textareaElement.style.height =
		(textareaElement.scrollHeight < 150 ? textareaElement.scrollHeight : 150) +
		"px"; // Max height 150px for edit
}

async function handleSaveEdit(messageId, messageTextContainer) {
	const textarea = messageTextContainer.querySelector(".edit-message-textarea");
	const newContent = textarea.value.trim();

	if (!newContent) {
		// Optionally show an error to the user
		console.warn("Edited content cannot be empty.");
		return;
	}

	console.log(
		`Attempting to save edit for chatId: ${window.currentChatId}, messageId: ${messageId}`
	); // Log IDs

	try {
		const response = await fetch(
			`/chat/${window.currentChatId}/message/${messageId}/edit/`,
			{
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"X-CSRFToken": getCookie("csrftoken"), // Assumes getCookie is available globally (from chat.js)
					"X-Requested-With": "XMLHttpRequest"
				},
				body: JSON.stringify({ new_content: newContent })
			}
		);

		if (!response.ok) {
			const errorData = await response.json();
			console.error(
				"Error saving edit:",
				errorData.error || response.statusText
			);
			// Optionally revert UI or show error to user
			alert(`Error saving message: ${errorData.error || "Server error"}`);
			return;
		}

		const data = await response.json();

		// 1. Update the message text in the UI
		const textElement = messageTextContainer.querySelector(
			".message-content-text"
		);
		textElement.textContent = data.new_content;
		toggleEditUI(messageTextContainer, false); // Hide edit controls, show new text

		// 2. Add/Update '(edited)' indicator
		let editedIndicator =
			messageTextContainer.querySelector(".edited-indicator");
		if (!editedIndicator) {
			editedIndicator = document.createElement("span");
			editedIndicator.className =
				"text-xs text-gray-400 italic ml-1 edited-indicator"; // Match template style
			// Insert after the <p> tag, before edit-controls if it were visible
			textElement.parentNode.insertBefore(
				editedIndicator,
				textElement.nextSibling.nextSibling
			); // A bit fragile, better to have a dedicated spot
		}
		if (editedIndicator.textContent != "(edited)") {
			editedIndicator.textContent = "(edited)";
		} else {
			return;
		}

		// 3. Remove all subsequent messages from the UI
		let currentMessageElement = messageTextContainer.closest(".message-enter");
		const messagesToRemove = [];
		while (currentMessageElement.nextElementSibling) {
			messagesToRemove.push(currentMessageElement.nextElementSibling);
			currentMessageElement = currentMessageElement.nextElementSibling;
		}
		messagesToRemove.forEach((msgEl) => msgEl.remove());

		// 4. Re-prompt the LLM with the new content
		await rePromptAfterEdit(data.new_content);
	} catch (error) {
		console.error("Network or other error saving edit:", error);
		alert("Failed to save message due to a network or client-side error.");
	}
}

async function rePromptAfterEdit(editedContent) {
	// This function is similar to the main form submission in chat.js,
	// but simplified for re-prompting after an edit.

	// Ensure global elements from chat.js are accessible or re-fetched if needed
	const stopButton = document.getElementById("stop-button"); // from chat.js

	// Assuming createTypingIndicator and handleStreamResponse are available globally from chat.js
	// If not, they might need to be passed or made globally accessible (e.g., window.createTypingIndicator)
	if (
		typeof createTypingIndicator !== "function" ||
		typeof handleStreamResponse !== "function"
	) {
		console.error(
			"Helper functions (createTypingIndicator, handleStreamResponse) not found globally."
		);
		alert("Critical error: Cannot re-prompt. UI functions missing.");
		return;
	}
	if (typeof smoothScrollToBottom !== "function") {
		// also from chat.js
		console.warn(
			"smoothScrollToBottom not found globally, scrolling might be jerky."
		);
	}

	createTypingIndicator();
	if (stopButton) stopButton.classList.remove("hidden");

	// Abort controller for this specific re-prompt stream
	// Note: chat.js also uses a global 'abortController'. Avoid conflict if this runs concurrently.
	// For simplicity, we'll assume this new stream replaces any ongoing one from main input.
	// If a global abortController is used in chat.js, it should be updated here too.
	// Or, make abortController an argument to handleStreamResponse.
	// For now, let's use a local one.
	const localAbortController = new AbortController();
	if (stopButton) {
		// If stop button exists, make it control this new stream
		// Remove previous listeners if any to avoid multiple aborts
		// This is a simplification; a more robust solution would manage listeners better
		const newStopButton = stopButton.cloneNode(true);
		stopButton.parentNode.replaceChild(newStopButton, stopButton);
		newStopButton.addEventListener("click", () => localAbortController.abort());
	}

	try {
		const formData = new FormData();
		formData.append("prompt", editedContent); // The edited content is the new prompt
		formData.append(
			"csrfmiddlewaretoken",
			getCookie("csrftoken") // Assumes getCookie is global
		);
		formData.append("is_reprompt_after_edit", "true"); // Indicate this is a re-prompt

		// Add rag_mode_active if needed by your stream endpoint and it's tracked globally
		if (typeof window.isRAGActive !== "undefined") {
			formData.append("rag_mode_active", window.isRAGActive);
		}

		const streamResponse = await fetch(
			`/chat/${window.currentChatId}/stream/`,
			{
				method: "POST",
				body: formData,
				headers: {
					"X-CSRFToken": getCookie("csrftoken")
					// "X-Requested-With": "XMLHttpRequest" // Not strictly necessary for FormData typically
				},
				signal: localAbortController.signal
			}
		);

		// handleStreamResponse is expected to be global from chat.js
		// It also handles removing typing indicator and stop button visibility on completion/error.
		await handleStreamResponse(streamResponse);
	} catch (error) {
		console.error("Error during re-prompt after edit:", error);
		if (typeof removeTypingIndicator === "function") removeTypingIndicator(); // from chat.js
		if (error.name !== "AbortError") {
			// appendMessage is also from chat.js
			if (typeof appendMessage === "function") {
				// appendMessage in chat.js takes (role, content) and returns the message container
				const errorContainer = appendMessage("assistant", ""); // Create container
				if (errorContainer)
					errorContainer.innerHTML = `<p class="text-red-400">Error re-prompting: ${error.message}</p>`;
			} else {
				alert("Error re-prompting: " + error.message);
			}
		}
	} finally {
		if (stopButton) stopButton.classList.add("hidden"); // Ensure stop button is hidden
		if (typeof smoothScrollToBottom === "function") smoothScrollToBottom();
	}
}

// Assumes getCookie is defined globally, e.g., in chat.js or common.js
// If not, it needs to be defined here or imported.
// function getCookie(name) { ... }

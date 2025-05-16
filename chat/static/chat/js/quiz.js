// quiz.js - Handles all quiz related functionality

// Depends on global: window.getCookie, window.appendSystemNotification, 
// window.createTypingIndicator, window.removeTypingIndicator, window.smoothScrollToBottom,
// window.currentChatId, window.isNewChat

// Centralized function to initialize quiz forms within a given parent element
// Made globally available for message_handler.js to call
window.initializeQuizForms = function(parentElement) {
	const quizForms = parentElement.querySelectorAll(".quiz-question form");
	quizForms.forEach((form) => {
		// Prevent multiple listeners if function is called multiple times on same element
		if (form.dataset.quizInitialized) return;
		form.dataset.quizInitialized = "true";

		form.addEventListener("submit", function (e) {
			e.preventDefault();
			const questionDiv = this.closest(".quiz-question");
			const correctAnswer = questionDiv.dataset.correct;
			const selectedAnswer = this.querySelector(
				'input[type="radio"]:checked'
			)?.value;

			const feedbackDiv = questionDiv.querySelector(".quiz-feedback");
			if (feedbackDiv) {
				if (selectedAnswer === correctAnswer) {
					feedbackDiv.textContent = "Correct!";
					feedbackDiv.className = "quiz-feedback mt-1.5 text-green-400";
				} else {
					feedbackDiv.textContent = "Incorrect. Try again!";
					feedbackDiv.className = "quiz-feedback mt-1.5 text-red-400";
				}
			}
		});
	});
};

// Utility: Fix quiz-message blocks that are wrapped in <pre><code>
// Made globally available for message_handler.js to call
window.unwrapQuizMessageCodeBlocks = function(quizMsgElement) {
	const elements = quizMsgElement
		? [quizMsgElement]
		: document.querySelectorAll(".quiz-message");

	elements.forEach((quizMsg) => {
		const pre = quizMsg.querySelector("pre");
		const code = pre ? pre.querySelector("code") : null;
		if (pre && code) {
			const temp = document.createElement("div");
			temp.innerHTML = code.innerHTML; // Use innerHTML to preserve actual tags
			const divs = temp.querySelectorAll("div.quiz-question, div.quiz-message"); // More specific selector
			if (divs.length > 0) {
				// Move all found divs out of pre/code and into quizMsg directly
				divs.forEach((div) => quizMsg.appendChild(div));
				pre.remove(); // Remove the pre wrapper
			}
		}
	});
};

// Made globally available for message_handler.js to call
window.fixEscapedQuizMessages = function(quizMsgElement) {
	const elements = quizMsgElement
		? quizMsgElement.querySelectorAll("pre code") // More targeted if element is passed
		: document.querySelectorAll(".quiz-message pre code");

	elements.forEach((code) => {
		const html = code.innerHTML.trim(); // innerHTML to get potentially escaped entities
		if (
			html.startsWith('&lt;div class="quiz-question"') ||
			html.startsWith('&lt;div class="quiz-message"')
		) {
			const temp = document.createElement("textarea");
			temp.innerHTML = html; // textarea decodes entities
			const unescaped = temp.value;
			
			const quizMsg = code.closest(".quiz-message");
			if (quizMsg) {
				quizMsg.innerHTML = unescaped; // Replace the whole quiz message content
			}
		}
	});
};

// Made globally available for message_handler.js to call
window.fixFirstLineQuizPreCode = function(quizMsgElement) {
	const elements = quizMsgElement
		? [quizMsgElement] // Process only the given element if provided
		: document.querySelectorAll(".quiz-message");

	elements.forEach((quizMsg) => {
		const pre = quizMsg.querySelector("pre");
		const code = pre ? pre.querySelector("code") : null;
		if (pre && code) {
			// Check if the <pre> is the very first child of the quiz-message
			// and if its content starts with a div tag (potentially escaped)
			const isFirstChildPre = pre === quizMsg.firstElementChild;
			const codeContent = code.textContent.trim(); // Use textContent for check

			if (isFirstChildPre && codeContent.startsWith('<div class="quiz-question"')) {
				const temp = document.createElement("textarea");
				temp.innerHTML = code.innerHTML; // Use innerHTML to get original content (with entities)
				const unescapedHtml = temp.value; // Decode entities
				
				// Replace the entire quiz message content with the unescaped HTML from the code block
				quizMsg.innerHTML = unescapedHtml;
				// No need to remove `pre` explicitly as we replaced the whole innerHTML
			}
		}
	});
};


document.addEventListener("DOMContentLoaded", function () {
	const quizButton = document.getElementById("quiz-button");
	const quizButtonContainer = document.getElementById("quiz-button-container");

	// Initialize existing quizzes on page load (e.g. from history)
	// Call the global functions now available on window
	document.querySelectorAll(".quiz-message").forEach(quizMessageElement => {
		if(window.unwrapQuizMessageCodeBlocks) window.unwrapQuizMessageCodeBlocks(quizMessageElement);
		if(window.fixEscapedQuizMessages) window.fixEscapedQuizMessages(quizMessageElement);
		if(window.fixFirstLineQuizPreCode) window.fixFirstLineQuizPreCode(quizMessageElement);
		if(window.initializeQuizForms) window.initializeQuizForms(quizMessageElement);
	});

	// Quiz Button Event Listener
	if (quizButton) {
		quizButton.addEventListener("click", async function () {
			if (
				window.currentChatId &&
				window.currentChatId !== "new" &&
				!window.isNewChat
			) {
				if(typeof window.createTypingIndicator === 'function') window.createTypingIndicator();
				try {
					const response = await fetch(`/chat/${window.currentChatId}/quiz/`, {
						method: "POST",
						headers: {
							"X-CSRFToken": window.getCookie("csrftoken")
						}
					});
					if(typeof window.removeTypingIndicator === 'function') window.removeTypingIndicator();

					if (response.ok) {
						const data = await response.json();
						if (data.quiz_html) {
							const messagesDiv = document.getElementById("chat-messages");
							const messageDiv = document.createElement("div");
							messageDiv.className = "message-enter px-4 md:px-6 py-6";
							messageDiv.setAttribute("data-message-id", data.message_id); // Store message ID

							const iconHtml = `<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white"><img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7"></div>`;
							const actualContentHtml = `<div class="quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl" data-message-id="${data.message_id}">${data.quiz_html}</div>`;

							messageDiv.innerHTML = `
								<div class="chat-container flex gap-4 md:gap-6">
									<div class="flex-shrink-0 w-7 h-7">${iconHtml}</div>
									<div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]">${actualContentHtml}</div>
								</div>`;
							messagesDiv.appendChild(messageDiv);

							const quizMessageElement = messageDiv.querySelector(".quiz-message");
							if (quizMessageElement) {
								if(window.unwrapQuizMessageCodeBlocks) window.unwrapQuizMessageCodeBlocks(quizMessageElement);
								if(window.fixEscapedQuizMessages) window.fixEscapedQuizMessages(quizMessageElement);
								if(window.fixFirstLineQuizPreCode) window.fixFirstLineQuizPreCode(quizMessageElement);
								if(window.initializeQuizForms) window.initializeQuizForms(quizMessageElement);
							}
							if(typeof window.smoothScrollToBottom === 'function') window.smoothScrollToBottom();
						} else if (data.error) {
							if(typeof window.appendSystemNotification === 'function') window.appendSystemNotification(`Error generating quiz: ${data.error}`, "error");
						} else {
							if(typeof window.appendSystemNotification === 'function') window.appendSystemNotification("Received an unexpected response for the quiz.", "error");
						}
					} else {
						let errorText = "Failed to generate quiz. Server error.";
						try {
							const errorData = await response.json();
							errorText = errorData.error || response.statusText;
						} catch (e) { /* Keep default */ }
						if(typeof window.appendSystemNotification === 'function') window.appendSystemNotification(`Error generating quiz: ${errorText}`, "error");
					}
				} catch (error) {
					if(typeof window.removeTypingIndicator === 'function') window.removeTypingIndicator();
					console.error("Error fetching quiz:", error);
					if(typeof window.appendSystemNotification === 'function') window.appendSystemNotification(`Error fetching quiz: ${error.message}`, "error");
				}
			} else {
				if(typeof window.appendSystemNotification === 'function') window.appendSystemNotification("Please start a chat first to generate a quiz.", "info");
			}
		});
	} else {
		console.warn("Quiz button not found in DOM for quiz.js");
	}

	// Quiz button visibility based on chat state
	// window.isNewChat and window.currentChatId are expected to be set by chat.js or chat_config.js
	// This can also be managed by chat_actions.js now if preferred, for centralization.
	// For now, keeping it here as it's quiz-specific UI.
	function updateQuizButtonVisibility() {
        if (quizButtonContainer) {
            if (window.isNewChat || !window.currentChatId || window.currentChatId === 'new') {
                quizButtonContainer.classList.add("hidden");
            } else {
                quizButtonContainer.classList.remove("hidden");
            }
        }
    }
    // Initial call to set visibility
    updateQuizButtonVisibility();

	// Listen for custom event if chat state changes (e.g., new chat created, chat loaded)
    // This is an example, the actual event name would depend on how chat.js or other modules signal this.
    document.addEventListener('chatStateChanged', function(event) {
        // event.detail might contain { isNewChat: true/false, currentChatId: '...' }
        if (event.detail) {
            window.isNewChat = event.detail.isNewChat;
            window.currentChatId = event.detail.currentChatId;
        }
        updateQuizButtonVisibility();
    });
});

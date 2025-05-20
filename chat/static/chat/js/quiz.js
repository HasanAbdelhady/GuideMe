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


document.addEventListener("DOMContentLoaded", function() {
	const chatMessages = document.getElementById("chat-messages");

	// Function to initialize event listeners for quiz forms within a given parent element
	function initializeQuizForms(parentElement) {
		const quizForms = parentElement.querySelectorAll(".quiz-question form");
		quizForms.forEach(form => {
			// Prevent multiple listeners if function is called multiple times on same element
			if (form.dataset.quizInitialized) return;
			form.dataset.quizInitialized = "true";

			form.addEventListener("submit", function(e) {
				e.preventDefault();
				const questionDiv = this.closest(".quiz-question");
				const correctAnswer = questionDiv.dataset.correct;
				const selectedAnswer = this.querySelector('input[type="radio"]:checked')?.value;
				
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
	}
	
	// Initial call for quiz forms already on the page
	if (chatMessages) {
		initializeQuizForms(chatMessages);
	}

	// Use MutationObserver to detect when new quiz messages are added to the DOM
	if (chatMessages) {
		const observer = new MutationObserver(mutations => {
			mutations.forEach(mutation => {
				if (mutation.type === "childList") {
					mutation.addedNodes.forEach(node => {
						if (node.nodeType === 1) { // Check if it's an element node
							// If the added node itself is a quiz message or contains quiz forms
							if (node.querySelector(".quiz-question form") || node.classList.contains("quiz-message")) {
								initializeQuizForms(node);
							}
							// Also check if child elements contain quiz forms (e.g., if a wrapper div is added)
							const nestedQuizForms = node.querySelectorAll(".quiz-question form");
							if (nestedQuizForms.length > 0) {
								initializeQuizForms(node);
							}
						}
					});
				}
			});
		});

		observer.observe(chatMessages, { childList: true, subtree: true });
	} else {
		console.warn("Chat messages container not found for MutationObserver in quiz.js.");
	}
});

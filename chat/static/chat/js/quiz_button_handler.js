// Quiz button and form initialization logic

// Centralized function to initialize quiz forms
function initializeQuizForms(parentElement) {
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
}
// Make it globally accessible as it might be called when new quiz messages are added dynamically
window.initializeQuizForms = initializeQuizForms;

document.addEventListener("DOMContentLoaded", function () {
    const quizButton = document.getElementById("quiz-button");
    const quizButtonContainer = document.getElementById("quiz-button-container");

    // Initialize quiz forms for any statically loaded quiz messages
    // This should ideally be called after messages are loaded/rendered.
    // If messages are loaded dynamically, this needs to be called after new quiz message is added.
    initializeQuizForms(document.body); 

    // Hide quiz button on new chat page initially or if no chat ID
    if (window.isNewChat || !window.currentChatId || window.currentChatId === 'new') {
        if(quizButtonContainer) quizButtonContainer.classList.add("hidden");
    }

    if (quizButton) {
        quizButton.addEventListener("click", async () => {
            if (!window.currentChatId || window.currentChatId === "new") {
                console.error("No active chat to generate quiz for.");
                // Optionally, show a user-friendly message
                // appendSystemNotification("Please start a conversation or select a chat to generate a quiz.", "error");
                return;
            }

            // Show some loading indicator if desired
            quizButton.disabled = true;
            quizButton.textContent = "Generating Quiz...";

            try {
                const response = await fetch(`/chat/${window.currentChatId}/quiz/`, {
                    method: "POST",
                    headers: {
                        "X-CSRFToken": window.getCookie("csrftoken"),
                        "Content-Type": "application/json",
                    },
                });

                if (!response.ok) {
                    const errorData = await response.json();
                    throw new Error(errorData.error || `HTTP error! status: ${response.status}`);
                }

                const data = await response.json();
                if (data.quiz_html) {
                    // Assuming appendMessage function is globally available from message_handler.js
                    if (window.appendMessage) {
                         window.appendMessage("assistant", "", data.message_id, "quiz", data.quiz_html);
                    } else {
                        console.error("appendMessage function not found. Cannot display quiz.");
                    }
                } else if (data.error) {
                    // appendSystemNotification(`Quiz Error: ${data.error}`, "error");
                    console.error("Quiz Error:", data.error);
                     alert(`Quiz Error: ${data.error}`); // Temporary alert
                }
            } catch (error) {
                console.error("Failed to generate quiz:", error);
                // appendSystemNotification(`Failed to generate quiz: ${error.message}`, "error");
                alert(`Failed to generate quiz: ${error.message}`); // Temporary alert
            } finally {
                quizButton.disabled = false;
                quizButton.textContent = "Quiz";
            }
        });
    }
}); 
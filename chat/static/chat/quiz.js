document.addEventListener("DOMContentLoaded", function () {
	const quizButton = document.getElementById("quiz-button");
	const chatMessages = document.getElementById("chat-messages");

	if (quizButton) {
		quizButton.addEventListener("click", async function () {
			quizButton.disabled = true;
			quizButton.textContent = "Generating...";
			try {
				const chatId = window.currentChatId;
				const response = await fetch(`/chat/${chatId}/quiz/`, {
					method: "POST",
					headers: {
						"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
							.value
					}
				});
				const data = await response.json();
				if (!response.ok) {
					alert(data.error || "Failed to generate quiz.");
				} else {
					appendQuizMessage(data.quiz_html);
				}
			} catch (e) {
				alert("Failed to generate quiz.");
			} finally {
				quizButton.disabled = false;
				quizButton.textContent = "Quiz";
			}
		});
	}

	function appendQuizMessage(quizHtml) {
		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter bg-[#444654] px-4 md:px-6 py-6";
		messageDiv.innerHTML = `
			<div class="chat-container flex gap-4 md:gap-6">
				<div class="flex-shrink-0 w-7 h-7">
					<div class="w-7 h-7 rounded-sm bg-[#11A27F] flex items-center justify-center text-white">
						<svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="h-5 w-5">
							<path d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-10.5V21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path>
						</svg>
					</div>
				</div>
				<div class="flex-1 overflow-x-auto min-w-0">
					<div class="quiz-message" style="margin-top: 0.5em;">${quizHtml}</div>
				</div>
			</div>
		`;
		chatMessages.appendChild(messageDiv);
		// Attach quiz interactivity
		initQuizInteractivity(messageDiv);
		window.scrollTo({ top: document.body.scrollHeight, behavior: "smooth" });
	}

	// --- Fix for reload: wrap orphan .quiz-question in .quiz-message ---
	document.querySelectorAll(".quiz-question").forEach(function (q) {
		if (!q.closest(".quiz-message")) {
			const wrapper = document.createElement("div");
			wrapper.className = "quiz-message";
			q.parentNode.insertBefore(wrapper, q);
			wrapper.appendChild(q);
		}
	});

	// Attach interactivity to all quiz messages on page load
	document.querySelectorAll(".quiz-message").forEach(initQuizInteractivity);

	function initQuizInteractivity(container) {
		// Find all quizzes in the container
		container.querySelectorAll(".quiz-question").forEach(function (question) {
			const form = question.querySelector("form");
			if (!form) return;
			const feedback = question.querySelector(".quiz-feedback");

			// Remove any previous submit event listeners by cloning
			const newForm = form.cloneNode(true);
			form.parentNode.replaceChild(newForm, form);
			const newFeedback = question.querySelector(".quiz-feedback");

			newForm.addEventListener("submit", function (e) {
				e.preventDefault();
				const selected = newForm.querySelector('input[type="radio"]:checked');
				if (!selected) {
					newFeedback.textContent = "Please select an answer.";
					newFeedback.className = "quiz-feedback text-yellow-400 mt-2";
					return;
				}
				const isCorrect = selected.value === question.dataset.correct;
				if (isCorrect) {
					newFeedback.textContent = "Correct!";
					newFeedback.className = "quiz-feedback text-green-400 mt-2";
					// Disable all radios and submit button after correct answer
					newForm
						.querySelectorAll('input[type="radio"]')
						.forEach((r) => (r.disabled = true));
					newForm.querySelector('button[type="submit"]').disabled = true;
				} else {
					newFeedback.textContent = "Incorrect. Try again!";
					newFeedback.className = "quiz-feedback text-red-400 mt-2";
					// Do NOT disable radios or submit button, allow retry
				}
			});
		});
	}
});

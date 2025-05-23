// Chat interface specific functionality
let chatConfig = { currentChatId: "new", isNewChat: true };
const configScript = document.getElementById("chat-config");
if (configScript) {
	try {
		chatConfig = JSON.parse(configScript.textContent);
	} catch (e) {
		console.error("Failed to parse chat config", e);
	}
}
let currentChatId = chatConfig.currentChatId;
let isNewChat = chatConfig.isNewChat;
window.currentChatId = currentChatId;
window.isNewChat = isNewChat;
let abortController = null;
let isRAGActive = false; // Default if nothing in localStorage
let isDiagramModeActive = false; // Default for Diagram mode

// Standard getCookie function (now global)
window.getCookie = function (name) {
	let cookieValue = null;
	if (document.cookie && document.cookie !== "") {
		const cookies = document.cookie.split(";");
		for (let i = 0; i < cookies.length; i++) {
			const cookie = cookies[i].trim();
			if (cookie.substring(0, name.length + 1) === name + "=") {
				cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
				break;
			}
		}
	}
	return cookieValue;
};

// Image modal functions - global scope for inline event handlers
function openImageModal(imgSrc) {
	// Create modal overlay if it doesn't exist
	let modalOverlay = document.getElementById("image-modal-overlay");
	if (!modalOverlay) {
		modalOverlay = document.createElement("div");
		modalOverlay.id = "image-modal-overlay";
		modalOverlay.className =
			"fixed inset-0 bg-black bg-opacity-80 z-50 flex items-center justify-center opacity-0 pointer-events-none transition-opacity duration-300";
		modalOverlay.innerHTML = `
			<div class="relative max-w-full max-h-full p-4 m-4">
				<img id="modal-image" src="" alt="Enlarged diagram" class="max-w-full max-h-[90vh] rounded-lg shadow-xl transform scale-95 transition-transform duration-300">
				<button id="close-image-modal" class="absolute top-0 right-0 -mt-4 -mr-4 bg-red-600 text-white rounded-full p-2 hover:bg-red-700 focus:outline-none">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-6 w-6" viewBox="0 0 24 24" fill="none" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		`;
		document.body.appendChild(modalOverlay);

		// Add event listener to close when clicked outside or on close button
		modalOverlay.addEventListener("click", (e) => {
			if (e.target === modalOverlay) {
				closeImageModal();
			}
		});
		document
			.getElementById("close-image-modal")
			.addEventListener("click", closeImageModal);
	}

	// Set the image source and show the modal
	const modalImage = document.getElementById("modal-image");
	modalImage.src = imgSrc;

	// Show the modal with animation
	modalOverlay.classList.remove("opacity-0", "pointer-events-none");
	setTimeout(() => {
		document.getElementById("modal-image").classList.remove("scale-95");
		document.getElementById("modal-image").classList.add("scale-100");
	}, 10);
}

function closeImageModal() {
	const modalOverlay = document.getElementById("image-modal-overlay");
	if (modalOverlay) {
		document.getElementById("modal-image").classList.remove("scale-100");
		document.getElementById("modal-image").classList.add("scale-95");
		modalOverlay.classList.add("opacity-0");
		setTimeout(() => {
			modalOverlay.classList.add("pointer-events-none");
		}, 300);
	}
}

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

// Wrap all logic in DOMContentLoaded
document.addEventListener("DOMContentLoaded", function () {
	console.log("Initializing chat.js");

	// Load saved states at the beginning, before initializing UI
	const savedRAGState = localStorage.getItem("ragModeActive");
	if (savedRAGState !== null) {
		isRAGActive = JSON.parse(savedRAGState);
		console.log("Loaded RAG state:", isRAGActive);
	} else {
		localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
	}

	const savedDiagramModeState = localStorage.getItem("diagramModeActive");
	if (savedDiagramModeState !== null) {
		isDiagramModeActive = JSON.parse(savedDiagramModeState);
		console.log("Loaded diagram mode state:", isDiagramModeActive);
	} else {
		localStorage.setItem(
			"diagramModeActive",
			JSON.stringify(isDiagramModeActive)
		);
	}

	// DOM elements
	const form = document.getElementById("chat-form");
	const textarea = document.getElementById("prompt");
	const stopButton = document.getElementById("stop-button");
	const fileInput = document.getElementById("file-input");
	const fileNameIndicator = document.getElementById("file-name");
	const clearFileButton = document.getElementById("clear-file");
	const sidebarToggle = document.getElementById("sidebar-toggle");
	const sidebar = document.getElementById("sidebar");
	const mainContent = document.getElementById("main-content");
	const ragToggleButton = document.getElementById("rag-mode-toggle");
	const manageRagContextBtn = document.getElementById("manage-rag-context-btn");
	const quizButton = document.getElementById("quiz-button");
	const quizButtonContainer = document.getElementById("quiz-button-container");
	const diagramModeToggleButton = document.getElementById(
		"diagram-mode-toggle"
	);
	const ragModalOverlay = document.getElementById("rag-modal-overlay");

	// Sidebar toggle
	let sidebarOpen = false;

	// Sidebar toggle button
	sidebarToggle.addEventListener("click", (e) => {
		e.stopPropagation();
		console.log("Sidebar toggle clicked");
		if (sidebar.classList.contains("-translate-x-full")) {
			sidebar.classList.remove("-translate-x-full");
			mainContent.classList.add("pl-64");
		} else {
			sidebar.classList.add("-translate-x-full");
			mainContent.classList.remove("pl-64");
		}
	});

	// Close sidebar button
	document.getElementById("close-sidebar").addEventListener("click", (e) => {
		e.stopPropagation();
		closeSidebar();
	});

	// Functions to handle sidebar state
	function openSidebar() {
		sidebarOpen = true;
		sidebar.classList.remove("-translate-x-full");
		mainContent.classList.add("pl-64");
	}

	function closeSidebar() {
		sidebarOpen = false;
		sidebar.classList.add("-translate-x-full");
		mainContent.classList.remove("pl-64");
	}

	// Click outside to close
	document.addEventListener("click", (e) => {
		const clickedSidebar = sidebar.contains(e.target);
		const clickedToggle = sidebarToggle.contains(e.target);

		// Only close if clicking outside both sidebar and toggle button
		if (sidebarOpen && !clickedSidebar && !clickedToggle) {
			closeSidebar();
		}
	});

	// Auto-resize textarea (now global for main prompt)
	window.adjustMainTextareaHeight = function () {
		textarea.style.height = "auto";
		textarea.style.height =
			(textarea.scrollHeight < 200 ? textarea.scrollHeight : 200) + "px";
	};

	textarea.addEventListener("input", window.adjustMainTextareaHeight);
	textarea.addEventListener("focus", window.adjustMainTextareaHeight);

	// Submit form on Enter (without Shift)
	textarea.addEventListener("keydown", function (e) {
		if (e.key === "Enter" && !e.shiftKey) {
			e.preventDefault();
			form.dispatchEvent(new Event("submit"));
		}
	});

	// Typing indicator
	window.createTypingIndicator = function () {
		window.removeTypingIndicator(); // Use the global remove function

		const typingDiv = document.createElement("div");
		typingDiv.className = "message-enter px-4 md:px-6 py-6";
		typingDiv.id = "typing-indicator";

		typingDiv.innerHTML = `
			<div class="chat-container flex gap-4 md:gap-6">
				<div class="flex-shrink-0 w-7 h-7">
					<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white">
						<img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7">
					</div>
				</div>
				<div class="flex-1">
					<div class="typing-indicator">
						<span></span>
						<span></span>
						<span></span>
					</div>
				</div>
			</div>
		`;

		document.getElementById("chat-messages").appendChild(typingDiv);
		window.smoothScrollToBottom();
	};

	window.removeTypingIndicator = function () {
		const typingIndicator = document.getElementById("typing-indicator");
		if (typingIndicator) {
			typingIndicator.remove();
		}
	};

	// Smooth scroll
	window.smoothScrollToBottom = function () {
		window.scrollTo({
			top: document.body.scrollHeight,
			behavior: "smooth"
		});
	};

	// File handling
	function clearFileSelection() {
		fileInput.value = "";
		fileNameIndicator.textContent = "";
		clearFileButton.classList.add("hidden");
	}

	fileInput.addEventListener("change", () => {
		const file = fileInput.files[0];
		if (file) {
			fileNameIndicator.textContent = `Attached: ${file.name}`;
			clearFileButton.classList.remove("hidden");
		} else {
			clearFileSelection();
		}
	});

	clearFileButton.addEventListener("click", clearFileSelection);

	// Initialize textarea
	if (textarea.value) {
		window.adjustMainTextareaHeight();
	}

	// Append message
	window.appendMessage = function (
		role,
		content,
		messageId = null,
		type = "text",
		quizHtml = null
	) {
		const messagesContainer = document.getElementById("chat-messages");
		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		let contentElementToReturn = messageDiv; // Default to outer div

		if (role === "user") {
			// User message - right aligned
			messageDiv.innerHTML = `
				<div class="chat-container flex flex-row-reverse gap-4 md:gap-6 justify-start">
					<!-- User icon - right side -->
					<div class="flex-shrink-0 w-7 h-7">
						<div class="w-7 h-7 rounded-sm bg-[#5436DA] flex items-center justify-center text-white text-xs font-semibold">U</div>
					</div>
					<!-- Message content -->
					<div class="overflow-x-auto max-w-[75%]">
						<div class="user-message text-gray-100 bg-[#444654] p-3 rounded-lg message-text-container" data-message-id="${
							messageId || ""
						}" data-created-at="${new Date().toISOString()}">
							<p class="whitespace-pre-wrap message-content-text">${content}</p>
							<div class="edit-controls hidden mt-2">
								<textarea class="edit-message-textarea w-full p-2 rounded bg-gray-700 border border-gray-600 text-gray-100 resize-none" rows="3"></textarea>
								<div class="flex justify-end gap-2 mt-2">
									<button class="cancel-edit-btn px-3 py-1 text-xs bg-gray-600 hover:bg-gray-500 rounded text-white">Cancel</button>
									<button class="save-edit-btn px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 rounded text-white">Save</button>
								</div>
							</div>
						</div>
						<!-- Edit button moved here, under the message box -->
						<div class="flex justify-end mt-1 pr-1">
							<button class="edit-message-btn p-1 text-gray-400 hover:text-gray-200 transition-opacity" data-message-id="${
								messageId || ""
							}" title="Edit message">
								<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
									<path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
								</svg>
							</button>
						</div>
					</div>
				</div>
			`;
		} else {
			// Assistant message - left aligned
			messageDiv.innerHTML = `
				<div class="chat-container flex gap-4 md:gap-6">
					<!-- Assistant icon - left side -->
				<div class="flex-shrink-0 w-7 h-7">
						<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white">
							<img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7">
				</div>
					</div>
					<!-- Message content -->
					<div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]" data-role="assistant-content-wrapper">
						${
							type === "quiz"
								? `<div class="quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl">${quizHtml}</div>`
								: type === "diagram"
								? `<div class="diagram-message-container bg-gray-800/50 p-2 my-2 rounded-lg shadow-md flex flex-col justify-center items-center">
								<img src="${content}" alt="Generated Diagram" class="max-w-full h-auto rounded-md mb-1 cursor-pointer hover:opacity-90 transition-opacity" onclick="openImageModal('${content}')">
								${
									messageId
										? `<p class="text-xs text-gray-400 italic mt-1 text-center">${messageId}</p>`
										: ""
								}
							</div>`
								: `<div class="max-w-none markdown-content text-gray-100">${content}</div>`
						}
				</div>
			</div>
		`;

			if (type === "text") {
				// For assistant text messages, we want to return the actual content div for streaming updates
				const markdownContentDiv =
					messageDiv.querySelector(".markdown-content");
				if (markdownContentDiv) {
					contentElementToReturn = markdownContentDiv;
					// Initialize raw text buffer for streaming, NO LONGER sanitize initial content
					// const sanitizedInitialContent = content.replace(/\n/g, ' '); // REMOVED
					markdownContentDiv.dataset.rawTextBuffer = content; // Use content directly
					// Initial parse
					if (typeof marked !== "undefined") {
						marked.setOptions({ breaks: false, gfm: true });
						markdownContentDiv.innerHTML = marked.parse(content); // Use content directly
						if (typeof hljs !== "undefined") {
							markdownContentDiv
								.querySelectorAll("pre code")
								.forEach((block) => {
									hljs.highlightElement(block);
								});
						}
						initializeCodeBlockFeatures(markdownContentDiv);
					} else {
						markdownContentDiv.textContent = content; // Fallback if no marked
					}
				}
			} else if (type === "quiz") {
				// If this is a quiz message, initialize it immediately
				setTimeout(() => {
					const quizMessageElement = messageDiv.querySelector(".quiz-message");
					if (quizMessageElement) {
						// Apply quiz-specific fixes
						unwrapQuizMessageCodeBlocks(quizMessageElement);
						fixEscapedQuizMessages(quizMessageElement);
						fixFirstLineQuizPreCode(quizMessageElement);

						// Initialize any quiz-specific event listeners using the new function
						initializeQuizForms(quizMessageElement);
					}
				}, 0);
				contentElementToReturn =
					messageDiv.querySelector(".quiz-message") || messageDiv;
			} else if (type === "diagram") {
				contentElementToReturn =
					messageDiv.querySelector(".diagram-message-container") || messageDiv;
			}
		}

		messagesContainer.appendChild(messageDiv);
		window.smoothScrollToBottom();
		return contentElementToReturn; // Return the appropriate element
	};

	// New function to append system notifications
	function appendSystemNotification(message, level = "info") {
		const messagesDiv = document.getElementById("chat-messages");
		const notificationDiv = document.createElement("div");
		notificationDiv.className = `fixed top-5 w-full px-4 md:px-6 py-3`; // Less padding than full messages

		let bgColor = "bg-green-700/80"; // Default info
		let textColor = "text-white";
		let iconSvg = `
			<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
				<path stroke-linecap="round" stroke-linejoin="round" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
			</svg>`;

		if (level === "warning") {
			bgColor = "bg-yellow-600/30";
			textColor = "text-yellow-300";
			iconSvg = `
				<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
				</svg>`;
		} else if (level === "error") {
			bgColor = "bg-red-600/30";
			textColor = "text-red-300";
			iconSvg = `
				<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5 mr-2 flex-shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
					<path stroke-linecap="round" stroke-linejoin="round" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
				</svg>`;
		}

		notificationDiv.innerHTML = `
			<div class="flex items-center justify-center max-w-2xl mx-auto p-2.5 rounded-lg ${bgColor} ${textColor} text-sm shadow">
				${iconSvg}
				<span>${message}</span>
			</div>
		`;
		document.body.appendChild(notificationDiv);
		setTimeout(() => {
			notificationDiv.remove();
		}, 1500);
		window.smoothScrollToBottom();
	}

	function updateAssistantMessage(container, contentChunk) {
		// container is now expected to be the specific div holding the content
		// e.g., the .markdown-content div for text, or .quiz-message for quizzes
		if (container) {
			const isQuizContent = container.classList.contains("quiz-message");

			if (isQuizContent) {
				// For quiz, contentChunk is expected to be the full HTML. Replace.
				container.innerHTML = contentChunk;
				// Re-apply quiz fixes and listeners if necessary, though usually quiz content is sent whole
				unwrapQuizMessageCodeBlocks(container);
				fixEscapedQuizMessages(container);
				fixFirstLineQuizPreCode(container);
				// Initialize quiz forms within this specific container
				initializeQuizForms(container);
			} else if (container.classList.contains("markdown-content")) {
				// For markdown text, append and re-parse
				// NO LONGER Sanitize the incoming chunk FIRST
				// const sanitizedContentChunk = contentChunk.replace(/\n/g, ' '); // REMOVED
				console.log(
					"Received contentChunk for update:",
					JSON.stringify(contentChunk)
				);

				// Use a data attribute to buffer raw text
				if (typeof container.dataset.rawTextBuffer === "undefined") {
					// This case should ideally be covered by appendMessage initializing the buffer
					container.dataset.rawTextBuffer = "";
				}
				container.dataset.rawTextBuffer += contentChunk; // Use contentChunk directly

				// Re-parse the entire accumulated content with marked
				// Ensure global 'marked' and 'hljs' are available or pass them/access them correctly
				if (typeof marked !== "undefined" && typeof hljs !== "undefined") {
					// Explicitly set marked.js options to ensure standard GFM behavior for newlines
					marked.setOptions({
						breaks: false, // GFM line breaks: single newlines are treated as spaces
						gfm: true // Use GitHub Flavored Markdown
					});
					const parsedHtml = marked.parse(container.dataset.rawTextBuffer); // Parse the full buffer
					console.log(
						"marked.parse() output (first 100 chars):",
						JSON.stringify(parsedHtml.substring(0, 100))
					);
					container.innerHTML = parsedHtml;
					// REMOVE/COMMENT OUT: container.textContent = container.dataset.rawTextBuffer;

					// Re-apply syntax highlighting to any new or existing code blocks
					container.querySelectorAll("pre code").forEach((block) => {
						hljs.highlightElement(block);
					});
					// Re-initialize code block features (copy, expand, etc.)
					initializeCodeBlockFeatures(container);
				} else {
					console.warn(
						"marked.js or highlight.js not available for markdown processing."
					);
					// Fallback to just showing text if markdown/highlighting isn't set up
					container.textContent = container.dataset.rawTextBuffer; // Ensure raw buffer is shown
				}
			} else {
				// Fallback for other types or if container is not what's expected
				// This case should ideally not be hit if appendMessage returns the correct element.
				// For safety, we can append if it seems like a text container.
				container.textContent += contentChunk;
			}
			window.smoothScrollToBottom();
		}
	}

	window.handleStreamResponse = async function (response) {
		const reader = response.body.getReader();
		const decoder = new TextDecoder();
		let buffer = "";
		let currentMessageContainer = null; // This will hold the .markdown-content div for the current assistant message
		let isFirstTextChunk = true;

		try {
			while (true) {
				const { value, done } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split("\n");
				buffer = lines.pop() || "";

				for (const line of lines) {
					if (line.startsWith("data: ")) {
						const data = JSON.parse(line.slice(6));

						if (data.type === "quiz") {
							// For now, let's assume quizzes are sent whole and handled by appendMessage
							if (isFirstTextChunk) {
								// Use isFirstTextChunk to ensure only one main message container is made
								appendMessage(
									"assistant",
									"", // Content is in quizHtml
									data.message_id,
									"quiz",
									data.quiz_html
								);
								isFirstTextChunk = false;
							}
						} else if (data.type === "content") {
							const messagesDiv = document.getElementById("chat-messages");
							if (isFirstTextChunk) {
								// Create the initial message container and get the .markdown-content div
								currentMessageContainer = appendMessage(
									"assistant",
									data.content, // First chunk goes here
									null,
									"text"
								);
								isFirstTextChunk = false;
								// The appendMessage function (as modified previously) already handles
								// sanitizing, setting rawTextBuffer, and initial parsing for this first chunk.
								// For this test, we let that happen for the first chunk.
							} else {
								// **RESTORED: Call updateAssistantMessage for subsequent chunks**
								// if (messagesDiv && data.content) { // Old diagnostic code
								// 	const newChunkParagraph = document.createElement('p');
								// 	newChunkParagraph.textContent = "CHUNK: " + data.content; // Prefix to make it obvious
								// 	newChunkParagraph.style.color = "cyan"; // Make it stand out
								// 	messagesDiv.appendChild(newChunkParagraph);
								// 	smoothScrollToBottom();
								// }
								updateAssistantMessage(currentMessageContainer, data.content);
							}
						} else if (data.type === "error") {
							appendSystemNotification(data.content, "error");
						} else if (data.type === "diagram_image") {
							// Handle diagram image message
							console.log("Received diagram image data:", data);
							if (data.diagram_image_id) {
								const imageUrl = `/chat/diagram_image/${data.diagram_image_id}/`; // Construct URL
								appendDiagramMessage(
									imageUrl,
									data.text_content || "Generated Diagram",
									data.message_id
								);
								isFirstTextChunk = false; // Ensure we don't create another message
							} else {
								appendSystemNotification(
									"Error: Received diagram response without diagram_image_id",
									"error"
								);
							}
						} else if (data.type === "done") {
							window.removeTypingIndicator();
						}
					}
				}
			}
		} catch (error) {
			console.error("Error processing stream:", error);
			appendSystemNotification(
				"An error occurred while processing the response.",
				"error"
			);
		} finally {
			window.removeTypingIndicator();
		}
	};

	function appendUserMessage(content) {
		const messagesDiv = document.getElementById("chat-messages");
		const placeholder = messagesDiv.querySelector(
			".flex.flex-col.items-center.justify-center"
		);
		if (placeholder) placeholder.remove();
		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		messageDiv.innerHTML = `
			<div class="chat-container flex flex-row-reverse gap-4 md:gap-6 justify-start">
				<div class="flex-shrink-0 w-7 h-7">
					<div class="w-7 h-7 rounded-sm bg-[#5436DA] flex items-center justify-center text-white text-xs font-semibold">U</div>
				</div>
				<div class="overflow-x-auto max-w-[75%]">
					<div class="user-message text-gray-100 bg-[#444654] p-3 rounded-lg">
						<p class="whitespace-pre-wrap">${content}</p>
					</div>
				</div>
			</div>
		`;
		messagesDiv.appendChild(messageDiv);
		window.smoothScrollToBottom();
	}

	form.addEventListener("submit", async function (e) {
		e.preventDefault();
		let promptText = textarea.value.trim();
		const fileData = fileInput.files[0];
		if (fileData) {
			promptText = promptText
				? `${promptText}\n\n[Attached file: ${fileData.name}]`
				: `[Attached file: ${fileData.name}]`;
		}
		if (!promptText && !fileData) return;
		appendUserMessage(promptText);
		textarea.value = "";
		window.adjustMainTextareaHeight();
		if (fileData) clearFileSelection();
		window.createTypingIndicator();
		stopButton.classList.remove("hidden");
		abortController = new AbortController();
		try {
			const formData = new FormData();
			formData.append("prompt", promptText);
			formData.append(
				"csrfmiddlewaretoken",
				document.querySelector("[name=csrfmiddlewaretoken]").value
			);
			if (fileData) formData.append("file", fileData);

			console.log("Submitting form with states:", {
				isRAGActive,
				isDiagramModeActive
			});

			formData.append("rag_mode_active", isRAGActive.toString());
			formData.append("diagram_mode_active", isDiagramModeActive.toString());

			if (isNewChat) {
				const createResponse = await fetch("/chat/create/", {
					method: "POST",
					body: formData,
					headers: {
						"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
							.value
					},
					signal: abortController.signal
				});
				if (!createResponse.ok) {
					throw new Error("Failed to create chat");
				}
				const data = await createResponse.json();
				if (!data.success) {
					throw new Error(data.error || "Failed to create chat");
				}
				history.pushState({}, "", data.redirect_url);
				currentChatId = data.chat_id;
				isNewChat = false;
				// Update global window variables that other modules might use
				window.currentChatId = currentChatId;
				window.isNewChat = isNewChat;

				// Update mobile header
				const mobileHeader = document.querySelector(".md\\:hidden h1");
				if (mobileHeader && data.title) {
					mobileHeader.textContent = data.title;
				}

				// Create and add new chat element to the sidebar
				const chatsList = document.getElementById("chats-list");
				const newChatElement = document.createElement("div");
				newChatElement.classList.add("group", "relative");
				newChatElement.dataset.chatId = data.chat_id;

				const currentDate = new Date().toLocaleDateString("en-US", {
					month: "short",
					day: "numeric",
					year: "numeric"
				});

				// Add a style tag to ensure group-hover works properly
				const styleTag = document.createElement("style");
				styleTag.textContent = `
						.group:hover .group-hover\\:opacity-100 {
							opacity: 1;
						}
					`;
				document.head.appendChild(styleTag);

				newChatElement.innerHTML = `
						<div class="flex items-center justify-between p-2 rounded hover:bg-gray-700/20 transition-colors">
							<a href="/chat/${data.chat_id}/" class="flex-1 truncate chat-title-container">
								<div class="text-lg text-gray-200 truncate chat-title" data-chat-id="${
									data.chat_id
								}">
									${data.title}
								</div>
							</a>
							<div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
								<button
									class="edit-title-btn p-1 text-gray-400 hover:text-gray-200 transition-all rounded"
									data-chat-id="${data.chat_id}" title="Rename chat">
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
									</svg>
								</button>
								<button
									class="delete-chat-btn p-1 text-gray-400 hover:text-gray-200 transition-all rounded"
									data-chat-id="${data.chat_id}" title="Delete chat">
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
										<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
									</svg>
								</button>
							</div>
						</div>
						<form method="POST" action="/chat/${
							data.chat_id
						}/update-title/" class="hidden edit-title-form absolute inset-0 flex items-center bg-gray-800 rounded-lg z-10">
							<input type="hidden" name="csrfmiddlewaretoken" value="${window.getCookie(
								"csrftoken"
							)}">
							<input type="text" name="title" value="${
								data.title
							}" class="flex-grow px-4 py-2 bg-transparent text-white focus:outline-none focus:ring-2 focus:ring-blue-500 rounded-lg" />
							<div class="flex items-center px-2">
								<button type="submit" class="p-2 text-green-400 hover:text-green-300 hover:bg-gray-700 rounded-lg transition-colors">
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7" /></svg>
								</button>
								<button type="button" class="cancel-edit p-2 text-red-400 hover:text-red-300 hover:bg-gray-700 rounded-lg transition-colors">
									<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" /></svg>
								</button>
							</div>
						</form>
					`;

				if (chatsList && chatsList.firstChild) {
					chatsList.insertBefore(newChatElement, chatsList.firstChild);
				} else if (chatsList) {
					chatsList.appendChild(newChatElement);
				}

				// Apply consistent styling to the newly created chat element
				applyConsistentChatElementStyling(newChatElement);

				// Dispatch chatStateChanged event ONCE after all updates
				console.log(
					"Dispatching chatStateChanged event. isNewChat:",
					window.isNewChat,
					"currentChatId:",
					window.currentChatId
				);
				const chatStateChangedEvent = new CustomEvent("chatStateChanged", {
					detail: {
						isNewChat: window.isNewChat,
						currentChatId: window.currentChatId
					}
				});
				document.dispatchEvent(chatStateChangedEvent);
			}

			// Stream the response
			const streamResponse = await fetch(`/chat/${currentChatId}/stream/`, {
				method: "POST",
				body: formData, // formData now includes rag_mode_active and diagram_mode_active
				headers: {
					"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
						.value
				},
				signal: abortController.signal
			});
			await window.handleStreamResponse(streamResponse);
		} catch (error) {
			console.error("Error:", error);
			window.removeTypingIndicator();
			if (error.name !== "AbortError") {
				const messageDiv = document.createElement("div");
				messageDiv.className = "message-enter px-4 md:px-6 py-6";
				messageDiv.innerHTML = `
						<div class="chat-container flex gap-4 md:gap-6">
							<div class="flex-shrink-0 w-7 h-7">
								<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white">
									<img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7">
								</div>
							</div>
							<div class="flex-1 overflow-x-auto min-w-0">
								<p class="text-red-400">Error: ${error.message}</p>
							</div>
						</div>
					`;
				document.getElementById("chat-messages").appendChild(messageDiv);
			}
			stopButton.classList.add("hidden");
		}
	});

	// Function to apply consistent styling to chat elements
	function applyConsistentChatElementStyling(chatElement) {
		// Make sure the group class is applied
		if (!chatElement.classList.contains("group")) {
			chatElement.classList.add("group");
		}

		// Make sure the relative class is applied
		if (!chatElement.classList.contains("relative")) {
			chatElement.classList.add("relative");
		}

		// Make sure the group-hover functionality works
		const editButton = chatElement.querySelector(".edit-title-btn");
		const deleteButton = chatElement.querySelector(".delete-chat-btn");

		if (editButton) {
			// Add opacity-0 class if missing
			if (!editButton.classList.contains("opacity-0")) {
				editButton.classList.add("opacity-0");
			}

			// Add group-hover:opacity-100 class if missing
			if (!editButton.classList.contains("group-hover:opacity-100")) {
				editButton.classList.add("group-hover:opacity-100");
			}

			// Fallback with direct style manipulation
			editButton.style.opacity = "0";
			chatElement.addEventListener("mouseenter", () => {
				editButton.style.opacity = "1";
			});
			chatElement.addEventListener("mouseleave", () => {
				editButton.style.opacity = "0";
			});
		}

		if (deleteButton) {
			// Add opacity-0 class if missing
			if (!deleteButton.classList.contains("opacity-0")) {
				deleteButton.classList.add("opacity-0");
			}

			// Add group-hover:opacity-100 class if missing
			if (!deleteButton.classList.contains("group-hover:opacity-100")) {
				deleteButton.classList.add("group-hover:opacity-100");
			}

			// Fallback with direct style manipulation
			deleteButton.style.opacity = "0";
			chatElement.addEventListener("mouseenter", () => {
				deleteButton.style.opacity = "1";
			});
			chatElement.addEventListener("mouseleave", () => {
				deleteButton.style.opacity = "0";
			});
		}
	}

	stopButton.addEventListener("click", () => {
		if (abortController) {
			abortController.abort();

			stopButton.classList.add("hidden");
			window.removeTypingIndicator();
			appendMessage("assistant", `_Response stopped by user._`);
		}
	});

	document.getElementById("clear-chat").addEventListener("click", async () => {
		if (!confirm("Are you sure you want to clear this conversation?")) return;
		try {
			if (currentChatId && currentChatId !== "new") {
				const response = await fetch(`/chat/${currentChatId}/clear/`, {
					method: "POST",
					headers: {
						"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
							.value
					}
				});
				if (!response.ok) throw new Error("Failed to clear chat");
			}
			document.getElementById("chat-messages").innerHTML = `
					<div class="flex flex-col items-center justify-center h-[calc(100vh-200px)]">
						<svg width="48" height="48" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" class="text-gray-400 mb-2">
							<path d="M21 7.5l-9-5.25L3 7.5m18 0l-9 5.25m9-5.25v9l-9 5.25M3 7.5l9 5.25M3 7.5v9l9 5.25m0-10.5V21" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"></path>
						</svg>
						<p class="text-gray-400 text-sm">How can I help you today?</p>
					</div>
				`;
		} catch (error) {
			console.error("Error clearing chat:", error);
			alert("There was an error clearing the chat. Please try again.");
		}
	});

	const chatsList = document.getElementById("chats-list");
	if (chatsList) {
		chatsList.addEventListener("click", async function (e) {
			const deleteButton = e.target.closest(".delete-chat-btn");
			if (deleteButton) {
				e.preventDefault();
				e.stopPropagation();
				const chatId = deleteButton.dataset.chatId;

				// Show custom delete confirmation dialog
				const dialog = document.getElementById("delete-confirm-dialog");
				if (!dialog) return;

				// Position dialog near the clicked button
				const buttonRect = deleteButton.getBoundingClientRect();
				dialog.style.top = `${buttonRect.bottom + 5}px`;
				dialog.style.left = `${buttonRect.left - dialog.offsetWidth + 20}px`;
				dialog.classList.remove("hidden");

				// Store the chat ID and button reference for the confirm action
				dialog.dataset.chatId = chatId;
				dialog.dataset.buttonRect = JSON.stringify({
					top: buttonRect.top,
					left: buttonRect.left,
					width: buttonRect.width,
					height: buttonRect.height
				});

				// Setup cancel button
				const cancelBtn = document.getElementById("delete-cancel-btn");
				if (cancelBtn) {
					cancelBtn.onclick = function () {
						dialog.classList.add("hidden");
					};
				}

				// Setup confirm button
				const confirmBtn = document.getElementById("delete-confirm-btn");
				if (confirmBtn) {
					confirmBtn.onclick = async function () {
						dialog.classList.add("hidden");
						await deleteChatWithAnimation(chatId);
					};
				}

				// Close dialog when clicking outside
				document.addEventListener("click", function closeDialogOutside(event) {
					if (
						!dialog.contains(event.target) &&
						!deleteButton.contains(event.target)
					) {
						dialog.classList.add("hidden");
						document.removeEventListener("click", closeDialogOutside);
					}
				});
			}

			// Handle edit button clicks
			const editButton = e.target.closest(".edit-title-btn");
			if (editButton) {
				e.preventDefault();
				e.stopPropagation();
				const chatId = editButton.dataset.chatId;
				console.log(`Edit button clicked for chat ID: ${chatId}`);

				// First try to find the chat element as a parent of the edit button
				let chatElement = editButton.closest("[data-chat-id]");

				// If that fails, try to find it by query selector using the chat ID
				if (!chatElement) {
					// Try in both the sidebar and chat list
					const possibleElements = document.querySelectorAll(
						`[data-chat-id="${chatId}"]`
					);
					console.log(
						`Found ${possibleElements.length} possible chat elements`
					);

					// Use the first element that's not a button or title
					for (const el of possibleElements) {
						if (
							!el.classList.contains("edit-title-btn") &&
							!el.classList.contains("delete-chat-btn") &&
							!el.classList.contains("chat-title")
						) {
							chatElement = el;
							console.log(`Using element as chat element:`, chatElement);
							break;
						}
					}

					if (!chatElement) {
						console.warn(
							`Could not find chat element for edit button with chat ID: ${chatId}`
						);
						return;
					}
				}

				console.log(`Found chat element:`, chatElement);

				// Try multiple approaches to find the title element
				let titleElement = null;

				// Approach 1: Direct querySelector on the chat element
				titleElement = chatElement.querySelector(
					`.chat-title[data-chat-id="${chatId}"]`
				);

				// Approach 2: Any chat-title inside the chat element
				if (!titleElement) {
					titleElement = chatElement.querySelector(".chat-title");
				}

				// Approach 3: Find by attribute anywhere in the document
				if (!titleElement) {
					titleElement = document.querySelector(
						`.chat-title[data-chat-id="${chatId}"]`
					);
				}

				// Approach 4: Find any element with this chat ID
				if (!titleElement) {
					const allElementsWithChatId = document.querySelectorAll(
						`[data-chat-id="${chatId}"]`
					);
					console.log(
						`Found ${allElementsWithChatId.length} elements with chat ID ${chatId}:`,
						allElementsWithChatId
					);

					// Find the one that looks like a title (not the chat element itself or a button)
					for (const el of allElementsWithChatId) {
						if (
							el !== chatElement &&
							!el.classList.contains("edit-title-btn") &&
							!el.classList.contains("delete-chat-btn")
						) {
							titleElement = el;
							console.log(`Using element as fallback title:`, titleElement);
							break;
						}
					}
				}

				if (!titleElement) {
					console.warn(`Could not find title element for chat ID: ${chatId}`);
					return;
				}

				console.log(`Found title element:`, titleElement);

				// Try different approaches to find the title container
				let titleContainer = chatElement.querySelector(".chat-title-container");

				// If that fails, look for any element containing the chat title
				if (!titleContainer) {
					titleContainer = titleElement.parentElement;
					if (!titleContainer) {
						// If we still can't find it, just use the chat element as container
						titleContainer = chatElement;
						console.warn(
							`Using chat element as fallback container for chat ID: ${chatId}`
						);
					}
				}

				console.log(`Found title container:`, titleContainer);

				startTitleEditing(titleContainer, titleElement, chatId);
			}
		});
	} else {
		console.warn("Chat list container (for delete delegation) not found.");
	}

	// Function to delete chat with animation
	async function deleteChatWithAnimation(chatId) {
		console.log(`[chat.js] Attempting to delete chat ${chatId} with animation`);
		try {
			const chatElement = document.querySelector(`[data-chat-id="${chatId}"]`);
			if (!chatElement) {
				console.warn(
					`[chat.js] Could not find chat element for ${chatId} to animate.`
				);
				return;
			}

			// Start fade out animation
			chatElement.style.transition = "opacity 0.3s, transform 0.3s";
			chatElement.style.opacity = "0";
			chatElement.style.transform = "translateX(-20px)";

			// Wait for animation to complete before making API call
			setTimeout(async () => {
				try {
					const response = await fetch(`/chat/${chatId}/delete/`, {
						method: "POST",
						headers: {
							"X-CSRFToken": window.getCookie("csrftoken"),
							"Content-Type": "application/json"
						}
					});

					if (!response.ok) {
						const errorData = await response
							.json()
							.catch(() => ({ error: "Failed to delete chat" }));
						throw new Error(errorData.error || "Failed to delete chat");
					}

					// Remove the element from DOM after successful API call
					chatElement.remove();
					console.log(`[chat.js] Chat ${chatId} deleted and removed from DOM.`);

					// Redirect if we deleted the current chat
					if (chatId === window.currentChatId) {
						window.location.href = "/chat/new/";
					}
				} catch (error) {
					// Restore the element if API call fails
					chatElement.style.opacity = "1";
					chatElement.style.transform = "translateX(0)";
					console.error(
						`[chat.js] Error during chat deletion API call: ${error}`
					);
					if (typeof appendSystemNotification === "function") {
						appendSystemNotification(
							`Error deleting chat: ${error.message}`,
							"error"
						);
					} else {
						alert(
							`An error occurred when trying to delete the chat: ${error.message}`
						);
					}
				}
			}, 300); // Match transition duration
		} catch (error) {
			console.error(`[chat.js] Error in deleteChatWithAnimation: ${error}`);
			if (typeof appendSystemNotification === "function") {
				appendSystemNotification(
					`Error deleting chat: ${error.message}`,
					"error"
				);
			} else {
				alert(
					`An error occurred when trying to delete the chat: ${error.message}`
				);
			}
		}
	}

	// Function to start title editing
	function startTitleEditing(container, titleElement, chatId) {
		console.log(`Starting title editing for chat ID: ${chatId}`);
		console.log(`Container:`, container);
		console.log(`Title element:`, titleElement);

		// Get the current title from the element or use a default
		const currentTitle = titleElement
			? titleElement.textContent.trim()
			: "Untitled";
		console.log(`Current title: "${currentTitle}"`);

		const input = document.createElement("input");
		input.type = "text";
		input.value = currentTitle;
		input.className =
			"w-full bg-gray-700/70 text-sm rounded px-2 py-1 text-gray-100 focus:outline-none focus:ring-1 focus:ring-gray-400";

		// Check if we're in the sidebar or chat list view
		const isSidebar = container.closest("#sidebar") !== null;
		console.log(`Is in sidebar: ${isSidebar}`);

		// Replace the title element with the input
		if (titleElement) {
			titleElement.style.display = "none";
		}

		// Adjust input size based on where we are
		if (isSidebar) {
			input.style.fontSize = "1.125rem"; // Match the text-lg class
		}

		// Make sure the container is valid before appending
		if (container && container.appendChild) {
			container.appendChild(input);
			input.focus();
			input.select();

			input.addEventListener("blur", () =>
				finishTitleEditing(container, titleElement, input, currentTitle, chatId)
			);

			input.addEventListener("keydown", (e) => {
				if (e.key === "Enter") {
					e.preventDefault();
					input.blur();
				} else if (e.key === "Escape") {
					cancelTitleEditing(container, titleElement, input);
				}
			});
		} else {
			console.error(`Invalid container for chat ID: ${chatId}`);
		}
	}

	async function finishTitleEditing(
		container,
		titleElement,
		input,
		originalTitle,
		chatId
	) {
		const newTitle = input.value.trim();
		if (!newTitle || newTitle === originalTitle) {
			cancelTitleEditing(container, titleElement, input);
			return;
		}

		try {
			const response = await fetch(`/chat/${chatId}/update-title/`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"X-CSRFToken":
						document.querySelector("[name=csrfmiddlewaretoken]").value ||
						window.getCookie("csrftoken")
				},
				body: JSON.stringify({ title: newTitle })
			});

			if (!response.ok) throw new Error("Failed to update title");

			// Update the title element
			if (titleElement) {
				titleElement.textContent = newTitle;
				titleElement.style.display = "";
			}

			// Always remove the input
			if (input && input.parentNode) {
				input.remove();
			}

			// Update all instances of this chat title in the DOM
			document
				.querySelectorAll(`.chat-title[data-chat-id="${chatId}"]`)
				.forEach((el) => {
					if (el !== titleElement) {
						el.textContent = newTitle;
					}
				});

			if (chatId === currentChatId) {
				const mobileHeader = document.querySelector(".md\\:hidden h1");
				if (mobileHeader) mobileHeader.textContent = newTitle;
				document.title = `${newTitle} - AI Chat Interface`;
			}
		} catch (error) {
			console.error("Error updating chat title:", error);
			cancelTitleEditing(container, titleElement, input);
			alert("Failed to update chat title. Please try again.");
		}
	}

	function cancelTitleEditing(container, titleElement, input) {
		if (titleElement) {
			titleElement.style.display = "";
		}

		if (input && input.parentNode) {
			input.remove();
		}
	}

	document.querySelectorAll(".markdown-content").forEach((container) => {
		const rawContent = container.textContent;
		if (rawContent && !container.querySelector("pre, p, ul, ol, blockquote")) {
			try {
				container.textContent = rawContent;
			} catch (e) {
				console.error("Failed to parse markdown:", e);
			}
		}
	});

	document.querySelectorAll(".message-enter").forEach((msg) => {
		// Use a valid selector for the green assistant icon
		// Instead of querySelector('.w-7.h-7.rounded-sm.bg-[#11A27F]'), use attribute selector or classList check
		const icon = Array.from(msg.children).find(
			(child) =>
				child.querySelector && child.querySelector("[class*='bg-#11A27F']")
		);
		if (icon) {
			msg.classList.add("");
		}
	});

	window.scrollTo({ top: document.body.scrollHeight, behavior: "auto" });
	if (textarea.value) {
		window.adjustMainTextareaHeight();
	}

	// Unwrap quiz-message code blocks on load
	unwrapQuizMessageCodeBlocks();

	fixEscapedQuizMessages();
	fixFirstLineQuizPreCode();

	// Initialize all existing chat elements for consistent styling
	const existingChatElements = document.querySelectorAll(
		"#chats-list [data-chat-id]"
	);
	existingChatElements.forEach((chatElement) => {
		applyConsistentChatElementStyling(chatElement);
	});

	// Patch appendMessage to also fix after rendering (only once)
	if (!window._appendMessagePatched) {
		const origAppendMessage = appendMessage;
		appendMessage = function (role, content) {
			const result = origAppendMessage(role, content);
			fixEscapedQuizMessages();
			fixFirstLineQuizPreCode();
			// If it's an assistant message, its content might have been set and needs features.
			// The `result` from the modified appendMessage is the content container for assistant.
			if (role === "assistant" && result) {
				// Assuming marked and hljs have run or will run if it's markdown.
				// For safety, ensure this runs after any markdown parsing and highlighting.
				// This might need to be more targeted if appendMessage itself doesn't trigger hljs.
				// However, typically hljs is called on the container after marked.parse.
				setTimeout(() => {
					// Use a timeout to ensure DOM update and hljs completion
					if (typeof initializeCodeBlockFeatures === "function") {
						initializeCodeBlockFeatures(result);
					}
				}, 0);
			}
			return result;
		};
		window._appendMessagePatched = true;
	}

	// --- RAG Context Management UI --- //
	const ragModalContent = document.getElementById("rag-modal-content");
	const closeRagModalBtn = document.getElementById("close-rag-modal-btn");
	const ragFilesListDiv = document.getElementById("rag-files-list");
	const noRagFilesMessage = document.getElementById("no-rag-files-message");
	const ragFileInput = document.getElementById("rag-file-input");
	const uploadRagFileBtn = document.getElementById("upload-rag-file-btn");
	const ragFileCountSpan = document.getElementById("rag-file-count");
	const ragUploadSection = document.getElementById("rag-upload-section");
	const ragLimitReachedMessage = document.getElementById(
		"rag-limit-reached-message"
	);

	let currentRAGFiles = []; // To store {id: '...', name: '...'} objects
	const MAX_RAG_FILES = 3;

	function openRAGModal() {
		if (!ragModalOverlay || !ragModalContent) return;
		ragModalOverlay.classList.remove("opacity-0", "pointer-events-none");
		ragModalContent.classList.remove("scale-95");
		ragModalContent.classList.add("scale-100");
		fetchRAGFiles(); // Fetch files when modal opens
	}

	function closeRAGModal() {
		if (!ragModalOverlay || !ragModalContent) return;
		ragModalOverlay.classList.add("opacity-0");
		ragModalContent.classList.add("scale-95");
		ragModalContent.classList.remove("scale-100");
		setTimeout(() => {
			ragModalOverlay.classList.add("pointer-events-none");
		}, 300); // Corresponds to transition duration
	}

	function renderRAGFilesList(files) {
		if (!ragFilesListDiv || !noRagFilesMessage) return;
		currentRAGFiles = files;
		ragFilesListDiv.innerHTML = "";
		if (files.length === 0) {
			noRagFilesMessage.classList.remove("hidden");
		} else {
			noRagFilesMessage.classList.add("hidden");
			files.forEach((file) => {
				const fileEl = document.createElement("div");
				fileEl.className =
					"flex items-center justify-between bg-gray-700 p-2 rounded-md text-sm hover:bg-gray-600/80 transition-colors";
				fileEl.innerHTML = `
	          <span class=\"text-gray-200 truncate max-w-[80%]\" title=\"${file.name}\">${file.name}</span>
	          <button class=\"delete-rag-file-btn p-1 text-red-400 hover:text-red-300 rounded-full focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-50\" data-file-id=\"${file.id}\" title=\"Remove from RAG context\">
	            <svg xmlns=\"http://www.w3.org/2000/svg\" class=\"h-4 w-4\" fill=\"none\" viewBox=\"0 0 24 24\" stroke=\"currentColor\" stroke-width=\"2\">
	              <path stroke-linecap=\"round\" stroke-linejoin=\"round\" d=\"M6 18L18 6M6 6l12 12\" />
	            </svg>
	          </button>
	        `;
				ragFilesListDiv.appendChild(fileEl);
				const deleteBtn = fileEl.querySelector(".delete-rag-file-btn");
				if (deleteBtn) {
					deleteBtn.addEventListener("click", () =>
						handleDeleteRAGFile(file.id)
					);
				}
			});
		}
		updateRAGFileLimitView();
	}

	function updateRAGFileLimitView() {
		if (
			!ragFileCountSpan ||
			!ragUploadSection ||
			!ragLimitReachedMessage ||
			!ragFileInput ||
			!uploadRagFileBtn
		)
			return;
		ragFileCountSpan.textContent = currentRAGFiles.length;
		if (currentRAGFiles.length >= MAX_RAG_FILES) {
			ragUploadSection.classList.add("hidden");
			ragLimitReachedMessage.classList.remove("hidden");
			ragFileInput.disabled = true;
			uploadRagFileBtn.disabled = true;
		} else {
			ragUploadSection.classList.remove("hidden");
			ragLimitReachedMessage.classList.add("hidden");
			ragFileInput.disabled = false;
			uploadRagFileBtn.disabled = false;
		}
	}

	async function fetchRAGFiles() {
		if (isNewChat || !currentChatId || currentChatId === "new") {
			renderRAGFilesList([]);
			return;
		}
		// Placeholder: API call to GET /chat/<currentChatId>/rag-files/
		console.log("Fetching RAG files for chat:", currentChatId);
		// Simulated API call
		try {
			const response = await fetch(`/chat/${currentChatId}/rag-files/`);
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error || "Failed to fetch RAG files");
			}
			const files = await response.json();
			renderRAGFilesList(files);
		} catch (error) {
			console.error("Error fetching RAG files:", error);
			appendSystemNotification(
				"Could not load RAG files: " + error.message,
				"error"
			);
			renderRAGFilesList([]); // Show empty on error too
		}
	}

	async function handleRAGFileUpload() {
		if (isNewChat || !currentChatId || currentChatId === "new") return;
		const file = ragFileInput.files[0];
		if (!file) {
			appendSystemNotification(
				"Please upload a file to add to context.",
				"warning"
			);
			return;
		}
		console.log("Uploading RAG file:", file.name, "for chat:", currentChatId);

		const formData = new FormData();
		formData.append("file", file);
		formData.append(
			"csrfmiddlewaretoken",
			document.querySelector("[name=csrfmiddlewaretoken]").value
		);

		try {
			const response = await fetch(`/chat/${currentChatId}/rag-files/`, {
				method: "POST",
				body: formData,
				headers: {
					// 'Content-Type': 'multipart/form-data' is automatically set by browser for FormData
					"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
						.value // Django needs this for non-session auth too sometimes
				}
			});

			const data = await response.json();

			if (!response.ok) {
				throw new Error(
					data.error || `Failed to upload file (status: ${response.status})`
				);
			}

			if (data.success && data.file) {
				appendSystemNotification(
					`Successfully added '${data.file.name}' to context.`,
					"info"
				);
				fetchRAGFiles(); // Refresh the list
			} else {
				throw new Error(
					data.error || "Upload completed but response format was unexpected."
				);
			}
		} catch (error) {
			console.error("Error uploading RAG file:", error);
			appendSystemNotification(`Upload failed: ${error.message}`, "error");
		}

		ragFileInput.value = ""; // Clear the input
	}

	async function handleDeleteRAGFile(fileId) {
		if (isNewChat || !currentChatId || currentChatId === "new") return;
		if (
			!confirm(
				"Are you sure you want to remove this file from the RAG context?"
			)
		)
			return;
		console.log("Deleting RAG file:", fileId, "for chat:", currentChatId);

		try {
			const response = await fetch(
				`/chat/${currentChatId}/rag-files/${fileId}/delete/`,
				{
					method: "DELETE",
					headers: {
						"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
							.value,
						"Content-Type": "application/json"
					}
				}
			);

			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(
					errorData.error ||
						`Failed to delete RAG file (status: ${response.status})`
				);
			}

			// Assuming the response is successful (e.g., 204 No Content or a JSON with success)
			// const data = await response.json(); // If response has body
			// if (data.success) { // If response has body and a success flag
			appendSystemNotification(
				`Successfully removed file from context.`,
				"info"
			);
			fetchRAGFiles(); // Refresh the list
			// } else {
			//     throw new Error(data.error || 'Deletion reported unsuccessful by server.');
			// }
		} catch (error) {
			console.error("Error deleting file:", error);
			appendSystemNotification(
				`Failed to remove file: ${error.message}`,
				"error"
			);
		}
	}

	// Event Listeners
	if (manageRagContextBtn) {
		manageRagContextBtn.addEventListener("click", openRAGModal);
	}
	if (closeRagModalBtn) {
		closeRagModalBtn.addEventListener("click", closeRAGModal);
	}
	if (ragModalOverlay) {
		ragModalOverlay.addEventListener("click", function (event) {
			if (event.target === ragModalOverlay) {
				closeRAGModal();
			}
		});
	}
	if (uploadRagFileBtn) {
		uploadRagFileBtn.addEventListener("click", handleRAGFileUpload);
	}

	// RAG Toggle Button Logic
	if (ragToggleButton) {
		console.log("Found RAG toggle button", isRAGActive);

		const setActiveStyles = () => {
			console.log("Setting RAG active styles");
			// For icons, we change the SVG color
			if (ragToggleButton.querySelector("svg")) {
				ragToggleButton.querySelector("svg").classList.remove("text-gray-400");
				ragToggleButton.querySelector("svg").classList.add("text-green-400");
				ragToggleButton.classList.add("bg-gray-800"); // Add background for better visual feedback
			}
		};

		const setInactiveStyles = () => {
			console.log("Setting RAG inactive styles");
			// For icons, we reset the SVG color
			if (ragToggleButton.querySelector("svg")) {
				ragToggleButton.querySelector("svg").classList.remove("text-green-400");
				ragToggleButton.querySelector("svg").classList.add("text-gray-400");
				ragToggleButton.classList.remove("bg-gray-800"); // Remove background
			}
		};

		// Initial styling based on loaded/default state
		if (isRAGActive) {
			setActiveStyles();
		} else {
			setInactiveStyles();
		}

		ragToggleButton.addEventListener("click", () => {
			console.log("RAG button clicked, current state:", isRAGActive);
			isRAGActive = !isRAGActive;
			console.log("Toggling RAG mode to:", isRAGActive);

			if (isRAGActive) {
				setActiveStyles();
				// If RAG becomes active, disable other modes
				if (isDiagramModeActive) {
					isDiagramModeActive = false;
					updateDiagramModeToggleButtonStyle();
					localStorage.setItem(
						"diagramModeActive",
						JSON.stringify(isDiagramModeActive)
					);
				}
			} else {
				setInactiveStyles();
			}
			localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
			appendSystemNotification(
				`Context mode is now ${isRAGActive ? "ACTIVE" : "INACTIVE"}.`,
				"info"
			);
		});
	} else {
		console.warn("Context toggle button not found in the DOM");
	}

	// Diagram Mode Toggle Button Logic
	function updateDiagramModeToggleButtonStyle() {
		if (!diagramModeToggleButton) return;
		if (isDiagramModeActive) {
			console.log("Setting diagram mode active styles");
			if (diagramModeToggleButton.querySelector("svg")) {
				diagramModeToggleButton
					.querySelector("svg")
					.classList.remove("text-gray-400");
				diagramModeToggleButton
					.querySelector("svg")
					.classList.add("text-blue-400");
				diagramModeToggleButton.classList.add("bg-gray-800"); // Add background for better visual feedback
			}
		} else {
			console.log("Setting diagram mode inactive styles");
			if (diagramModeToggleButton.querySelector("svg")) {
				diagramModeToggleButton
					.querySelector("svg")
					.classList.remove("text-blue-400");
				diagramModeToggleButton
					.querySelector("svg")
					.classList.add("text-gray-400");
				diagramModeToggleButton.classList.remove("bg-gray-800"); // Remove background
			}
		}
	}

	if (diagramModeToggleButton) {
		console.log("Found diagram mode toggle button", isDiagramModeActive);

		updateDiagramModeToggleButtonStyle(); // Set initial style

		const setInactiveStyles = () => {
			console.log("Setting RAG inactive styles");
			// For icons, we reset the SVG color
			if (ragToggleButton.querySelector("svg")) {
				ragToggleButton.querySelector("svg").classList.remove("text-green-400");
				ragToggleButton.querySelector("svg").classList.add("text-gray-400");
				ragToggleButton.classList.remove("bg-gray-800"); // Remove background
			}
		};

		diagramModeToggleButton.addEventListener("click", () => {
			console.log(
				"Diagram mode button clicked, current state:",
				isDiagramModeActive
			);
			isDiagramModeActive = !isDiagramModeActive;
			console.log("Toggling diagram mode to:", isDiagramModeActive);

			updateDiagramModeToggleButtonStyle();
			if (isDiagramModeActive) {
				// If Diagram Mode becomes active, disable other modes
				if (isRAGActive) {
					isRAGActive = false;
					setInactiveStyles(); // Use the RAG inactive style function
					localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
				}
			}
			localStorage.setItem(
				"diagramModeActive",
				JSON.stringify(isDiagramModeActive)
			);
			appendSystemNotification(
				`Diagram mode is now ${isDiagramModeActive ? "ACTIVE" : "INACTIVE"}.`,
				"info"
			);
		});
	} else {
		console.warn("Diagram mode toggle button not found in the DOM");
	}

	// Initial calls for existing messages (if any)
	document.querySelectorAll(".markdown-content").forEach((messageElement) => {
		if (!messageElement.closest(".quiz-message")) {
			// Don't run on quiz HTML containers
			initializeCodeBlockFeatures(messageElement);
		}
	});
	// Initialize all quiz forms present on initial page load
	initializeQuizForms(document.getElementById("chat-messages"));
	hljs.highlightAll();
	if (document.getElementById("chat-messages").children.length > 1) {
		// more than just placeholder
		window.smoothScrollToBottom();
	}

	// --- RAG Context Modal ---
	// const manageRagContextBtn = document.getElementById("manage-rag-context-btn"); // REMOVE this redeclaration
	// const ragModalOverlay = document.getElementById("rag-modal-overlay"); // REMOVE this redeclaration
	if (manageRagContextBtn) {
		manageRagContextBtn.addEventListener("click", openRAGModal);
	}

	// Make sure this new function is defined in your JS
	function appendDiagramMessage(imageUrl, textContent, messageId) {
		const messagesDiv = document.getElementById("chat-messages");

		// Remove empty placeholder if present
		const placeholder = messagesDiv.querySelector(
			".flex.flex-col.items-center.justify-center"
		);
		if (placeholder) placeholder.remove();

		console.log(
			"Appending diagram message with constructed image URL:",
			imageUrl
		);

		// The imageUrl is now constructed with the correct path to the serving endpoint
		// No need for /media/ prefix check here as it's a direct path to the view

		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		messageDiv.setAttribute("data-message-id", messageId); // For potential future use

		messageDiv.innerHTML = `
				<div class="chat-container flex gap-4 md:gap-6">
					<div class="flex-shrink-0 w-7 h-7">
						<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white">
							<img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7">
						</div>
					</div>
					<div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]">
						<div class="diagram-message-container bg-gray-800/50 p-2 my-2 rounded-lg shadow-md flex flex-col justify-center items-center">
							<img src="${imageUrl}" alt="${textContent || "Generated Diagram"}" 
								class="max-w-full h-auto rounded-md mb-1 cursor-pointer hover:opacity-90 transition-opacity" 
								onclick="openImageModal('${imageUrl}')">
							${
								textContent
									? `<p class="text-xs text-gray-400 italic mt-1 text-center">${textContent}</p>`
									: ""
							}
						</div>
					</div>
				</div>
			`;

		messagesDiv.appendChild(messageDiv);
		window.smoothScrollToBottom();
	}

	// Make existing diagram images clickable
	document.querySelectorAll(".diagram-message-container img").forEach((img) => {
		if (!img.hasAttribute("onclick")) {
			img.classList.add(
				"cursor-pointer",
				"hover:opacity-90",
				"transition-opacity"
			);
			img.addEventListener("click", function () {
				openImageModal(this.src);
			});
		}
	});

	// Initialize chat configuration
	const chatConfigElement = document.getElementById("chat-config");
	if (chatConfigElement) {
		try {
			const config = JSON.parse(chatConfigElement.textContent);
			window.currentChatId = config.currentChatId;
			window.isNewChat = config.isNewChat;
		} catch (e) {
			console.error("Failed to parse chat config:", e);
			window.currentChatId = window.location.pathname.includes("/new/")
				? "new"
				: window.location.pathname.split("/").filter(Boolean).pop();
			window.isNewChat = window.currentChatId === "new";
		}
	} else {
		console.warn("Chat config script block not found. Inferring from URL.");
		window.currentChatId = window.location.pathname.includes("/new/")
			? "new"
			: window.location.pathname.split("/").filter(Boolean).pop();
		window.isNewChat = window.currentChatId === "new";
	}
	updateNewChatUI(window.isNewChat);

	// Initialize existing quizzes
	const existingQuizAreas = document.querySelectorAll(
		".quiz-render-area[data-quiz-json]"
	);
	existingQuizAreas.forEach((area) => {
		if (
			window.QuizRenderer &&
			typeof window.QuizRenderer.renderQuiz === "function"
		) {
			try {
				window.QuizRenderer.renderQuiz(area);
			} catch (e) {
				console.error("Error rendering existing quiz:", e, area);
				area.innerHTML =
					"<p class='text-red-400 p-2'>Error rendering quiz.</p>";
			}
		} else {
			console.error("QuizRenderer not available for existing quizzes.");
			area.innerHTML =
				"<p class='text-red-400 p-2'>Quiz display component failed to load.</p>";
		}
	});

	// Initialize quiz button if it exists
	if (quizButton) {
		console.log("Quiz button found, attaching click handler");
		quizButton.addEventListener("click", async function () {
			console.log("Quiz button clicked");
			if (
				window.currentChatId &&
				window.currentChatId !== "new" &&
				!window.isNewChat
			) {
				window.createTypingIndicator();
				try {
					const response = await fetch(`/chat/${window.currentChatId}/quiz/`, {
						method: "POST",
						headers: {
							"X-CSRFToken": getCookie("csrftoken")
						}
						// No body or Content-Type application/json per previous fixes
					});
					window.removeTypingIndicator();

					if (response.ok) {
						const data = await response.json();
						if (data.quiz_html) {
							const messagesDiv = document.getElementById("chat-messages");
							const messageDiv = document.createElement("div");
							messageDiv.className = "message-enter px-4 md:px-6 py-6";

							const iconHtml = `<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white"><img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7"></div>`;
							const actualContentHtml = `<div class="quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl">${data.quiz_html}</div>`;

							messageDiv.innerHTML = `
									<div class="chat-container flex gap-4 md:gap-6">
										<div class="flex-shrink-0 w-7 h-7">${iconHtml}</div>
										<div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]">${actualContentHtml}</div>
									</div>`;
							messagesDiv.appendChild(messageDiv);

							// Process the quiz content that was just added
							const quizMessageElement =
								messageDiv.querySelector(".quiz-message");
							if (quizMessageElement) {
								unwrapQuizMessageCodeBlocks(quizMessageElement);
								fixEscapedQuizMessages(quizMessageElement);
								fixFirstLineQuizPreCode(quizMessageElement);

								// Set up form handlers for the quiz using the new function
								initializeQuizForms(quizMessageElement);
							}

							window.smoothScrollToBottom();
						} else if (data.error) {
							appendSystemNotification(
								`Error generating quiz: ${data.error}`,
								"error"
							);
						} else {
							appendSystemNotification(
								"Received an unexpected response for the quiz.",
								"error"
							);
						}
					} else {
						let errorText = "Failed to generate quiz. Server error.";
						try {
							const errorData = await response.json();
							errorText = errorData.error || response.statusText;
						} catch (e) {
							// Keep default errorText if response is not JSON or parsing fails
							console.warn(
								"Could not parse error response as JSON for quiz generation failure."
							);
						}
						appendSystemNotification(
							`Error generating quiz: ${errorText}`,
							"error"
						);
					}
				} catch (error) {
					window.removeTypingIndicator();
					console.error("Error fetching quiz:", error);
					appendSystemNotification(
						`Error fetching quiz: ${error.message}`,
						"error"
					);
				}
			} else {
				appendSystemNotification(
					"Please start a chat first to generate a quiz.",
					"info"
				);
			}
		});
	} else {
		console.warn("Quiz button not found in DOM");
	}

	// Make quiz buttons visible/invisible based on chat state
	window.updateQuizButtonVisibility = function () {
		if (quizButtonContainer) {
			if (
				window.isNewChat ||
				!window.currentChatId ||
				window.currentChatId === "new"
			) {
				quizButtonContainer.classList.add("hidden");
			} else {
				quizButtonContainer.classList.remove("hidden");
			}
		}
	};
	// Initial call to set visibility
	window.updateQuizButtonVisibility();

	// Add an event listener for chatStateChanged to update UI elements
	document.addEventListener("chatStateChanged", function (event) {
		console.log(
			"[chat.js] Caught chatStateChanged event directly.",
			event.detail
		);
		if (typeof updateNewChatUI === "function") {
			updateNewChatUI(event.detail.isNewChat);
		}
	});
});

function updateNewChatUI(isNew) {
	const quizButtonContainer = document.getElementById("quiz-button-container");
	const manageRagButton = document.getElementById("manage-rag-context-btn");

	console.log("[updateNewChatUI from chat.js] Called with isNew:", isNew);

	if (isNew) {
		console.log("[updateNewChatUI from chat.js] HIDING buttons.");
		if (quizButtonContainer) {
			quizButtonContainer.classList.add("hidden");
		}
		if (manageRagButton) {
			manageRagButton.classList.add("hidden");
		}
	} else {
		// Defer the showing logic slightly
		setTimeout(() => {
			console.log(
				"[updateNewChatUI from chat.js - setTimeout] SHOWING buttons."
			);
			if (quizButtonContainer) {
				quizButtonContainer.classList.remove("hidden");
				quizButtonContainer.style.display = "";
				console.log(
					"[updateNewChatUI from chat.js - setTimeout] Quiz button hidden class removed. Hidden status:",
					quizButtonContainer.classList.contains("hidden")
				);
				console.log(
					"[updateNewChatUI from chat.js - setTimeout] Quiz button style.display:",
					quizButtonContainer.style.display
				);
			}
			if (manageRagButton) {
				manageRagButton.classList.remove("hidden");
				manageRagButton.style.display = "";
				console.log(
					"[updateNewChatUI from chat.js - setTimeout] RAG button hidden class removed. Hidden status:",
					manageRagButton.classList.contains("hidden")
				);
				console.log(
					"[updateNewChatUI from chat.js - setTimeout] RAG button style.display:",
					manageRagButton.style.display
				);
			}
		}, 0); // Zero delay, just defers to next tick
	}
}

// Utility: Fix quiz-message blocks that are wrapped in <pre><code>
function unwrapQuizMessageCodeBlocks(quizMsgElement) {
	// If no specific element provided, use all quiz messages
	const elements = quizMsgElement
		? [quizMsgElement]
		: document.querySelectorAll(".quiz-message");

	elements.forEach((quizMsg) => {
		const pre = quizMsg.querySelector("pre");
		const code = pre ? pre.querySelector("code") : null;
		if (pre && code) {
			// Find all <div> elements inside the code block
			const temp = document.createElement("div");
			temp.innerHTML = code.innerHTML;
			const divs = temp.querySelectorAll("div.quiz-question, div.quiz-message");
			if (divs.length > 0) {
				divs.forEach((div) => quizMsg.appendChild(div));
				pre.remove();
			}
		}
	});
}

function fixEscapedQuizMessages(quizMsgElement) {
	// If no specific element provided, use all quiz messages
	const elements = quizMsgElement
		? quizMsgElement.querySelectorAll("pre code")
		: document.querySelectorAll(".quiz-message pre code");

	elements.forEach((code) => {
		const html = code.innerHTML.trim();
		// Detect if it looks like escaped quiz HTML
		if (
			html.startsWith('&lt;div class="quiz-question"') ||
			html.startsWith('&lt;div class="quiz-message"')
		) {
			// Unescape HTML entities
			const temp = document.createElement("textarea");
			temp.innerHTML = html;
			const unescaped = temp.value;
			// Replace the parent .quiz-message content with real HTML
			const quizMsg = code.closest(".quiz-message");
			if (quizMsg) {
				quizMsg.innerHTML = unescaped;
			}
		}
	});
}

function fixFirstLineQuizPreCode(quizMsgElement) {
	// If no specific element provided, use all quiz messages
	const elements = quizMsgElement
		? [quizMsgElement]
		: document.querySelectorAll(".quiz-message");

	elements.forEach((quizMsg) => {
		const pre = quizMsg.querySelector("pre");
		const code = pre ? pre.querySelector("code") : null;
		if (pre && code) {
			// Only fix if the code block is the first child
			const isFirst = pre === quizMsg.firstElementChild;
			if (isFirst) {
				// Unescape HTML entities in the code block
				const temp = document.createElement("textarea");
				temp.innerHTML = code.textContent.trim();
				const unescaped = temp.value;
				// Remove the <pre> block
				pre.remove();
				// Prepend the unescaped line to the quiz-message's innerHTML
				quizMsg.innerHTML = unescaped + quizMsg.innerHTML;
			}
		}
	});
}

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
let isYoutubeModeActive = false; // Default for YouTube mode

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
	// Create modal if it doesn't exist
	let modalOverlay = document.getElementById("image-modal-overlay");
	if (!modalOverlay) {
		modalOverlay = document.createElement("div");
		modalOverlay.id = "image-modal-overlay";
		modalOverlay.className =
			"fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50";
		modalOverlay.innerHTML = `
			<div id="image-container" class="relative bg-gray-900 w-full h-full flex items-center justify-center">
				<img id="modal-image" src="" alt="Enlarged diagram"
					class="max-w-full max-h-full object-contain transition-transform duration-200 ease-in-out">
				
				<!-- Control buttons positioned on the left -->
				<div class="absolute left-4 top-1/2 transform -translate-y-1/2 flex flex-col gap-3 z-10">
					<button id="zoom-in-btn" class="bg-gray-800/90 text-white rounded-full p-3 hover:bg-gray-700 focus:outline-none transition-colors shadow-lg" title="Zoom In">
						<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM10 7v3m0 0v3m0-3h3m-3 0H7" />
						</svg>
					</button>
					<button id="zoom-out-btn" class="bg-gray-800/90 text-white rounded-full p-3 hover:bg-gray-700 focus:outline-none transition-colors shadow-lg" title="Zoom Out">
						<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0zM13 10H7" />
						</svg>
					</button>
					<button id="zoom-reset-btn" class="bg-gray-800/90 text-white rounded-full p-3 hover:bg-gray-700 focus:outline-none transition-colors shadow-lg" title="Reset Zoom">
						<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
							<path stroke-linecap="round" stroke-linejoin="round" d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
						</svg>
					</button>
				</div>
				
				<!-- Close button in top right -->
				<button id="close-image-modal" class="absolute top-4 right-4 bg-red-600/90 text-white rounded-full p-3 hover:bg-red-700 focus:outline-none transition-colors shadow-lg" title="Close">
					<svg xmlns="http://www.w3.org/2000/svg" class="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
						<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12" />
					</svg>
				</button>
			</div>
		`;
		document.body.appendChild(modalOverlay);

		// Set up zoom functionality first
		initializeImageZoom();

		// Add event listeners
		modalOverlay.addEventListener("click", function (e) {
			if (e.target === modalOverlay) {
				closeImageModal();
			}
		});

		document
			.getElementById("close-image-modal")
			.addEventListener("click", closeImageModal);

		// Add keydown listener
		document.addEventListener("keydown", handleImageModalKeydown);
	}

	// Set the image source and show the modal
	const modalImage = document.getElementById("modal-image");
	modalImage.src = imgSrc;

	// Reset zoom when opening new image - REMOVED, now handled by event listener in initializeImageZoom
	// resetImageZoom();

	modalOverlay.style.display = "flex";

	// Prevent body scroll when modal is open
	const container = document.getElementById("image-container");
	container.focus();
	document.body.style.overflow = "hidden";
}

function closeImageModal() {
	const modalOverlay = document.getElementById("image-modal-overlay");
	if (modalOverlay) {
		modalOverlay.style.display = "none";
		const container = document.getElementById("image-container");
		if (container) {
			container.blur();
		}
		// Restore body scroll
		document.body.style.overflow = "";
		// Remove keydown listener
		document.removeEventListener("keydown", handleImageModalKeydown);
	}
}

function initializeImageZoom() {
	const modalImage = document.getElementById("modal-image");
	const imageContainer = document.getElementById("image-container");

	if (!modalImage || !imageContainer) return;

	let currentScale = 1;
	let translateX = 0;
	let translateY = 0;
	let isDragging = false;
	let startX = 0;
	let startY = 0;
	let dragStartTranslateX = 0;
	let dragStartTranslateY = 0;

	let originalImageWidth = 0;
	let originalImageHeight = 0;

	function calculateFitScale() {
		// Use naturalWidth/Height for the true image size.
		originalImageWidth = modalImage.naturalWidth;
		originalImageHeight = modalImage.naturalHeight;

		if (!originalImageWidth || !originalImageHeight) {
			// Image not loaded yet or invalid
			return 1;
		}

		const containerWidth = imageContainer.clientWidth;
		const containerHeight = imageContainer.clientHeight;

		const scaleX = containerWidth / originalImageWidth;
		const scaleY = containerHeight / originalImageHeight;

		// Return the smaller scale to fit the entire image ("contain").
		// This allows upscaling for small images to fit the modal.
		return Math.min(scaleX, scaleY);
	}

	function updateCursor() {
		if (currentScale <= calculateFitScale()) {
			modalImage.style.cursor = isDragging ? "grabbing" : "grab";
		} else {
			modalImage.style.cursor = "zoom-in";
		}
	}

	// Apply transform to image with bounds checking
	function applyTransform() {
		// Calculate bounds to prevent dragging image out of view
		const containerRect = imageContainer.getBoundingClientRect();
		const imageWidth = originalImageWidth * currentScale;
		const imageHeight = originalImageHeight * currentScale;

		// Calculate maximum translation allowed to keep image edges within view
		const maxTranslateX = Math.max(
			0,
			(imageWidth - containerRect.width) / 2 / currentScale
		);
		const maxTranslateY = Math.max(
			0,
			(imageHeight - containerRect.height) / 2 / currentScale
		);

		// Clamp translation values
		translateX = Math.max(-maxTranslateX, Math.min(maxTranslateX, translateX));
		translateY = Math.max(-maxTranslateY, Math.min(maxTranslateY, translateY));

		modalImage.style.transform = `scale(${currentScale}) translate(${translateX}px, ${translateY}px)`;
		updateCursor();
	}

	function zoomInAtPoint(clientX = null, clientY = null) {
		if (currentScale >= 3) return; // Max zoom

		const oldScale = currentScale;
		currentScale *= 1.3;

		if (clientX !== null && clientY !== null) {
			// Zoom at the specified point
			const containerRect = imageContainer.getBoundingClientRect();
			// Point relative to image container center
			const pointX = clientX - containerRect.left - containerRect.width / 2;
			const pointY = clientY - containerRect.top - containerRect.height / 2;

			// Adjust translation to keep the point under the cursor
			const scaleFactor = currentScale / oldScale;
			translateX =
				(translateX - pointX / oldScale) * scaleFactor + pointX / currentScale;
			translateY =
				(translateY - pointY / oldScale) * scaleFactor + pointY / currentScale;
		}

		applyTransform();
	}

	function zoomOut() {
		if (currentScale <= calculateFitScale()) return; // Don't zoom out beyond fit
		currentScale /= 1.3;
		applyTransform();
	}

	// Create the resetImageZoom function and make it globally accessible
	window.resetImageZoom = function () {
		// Calculate the proper scale to fit the image in the container
		currentScale = calculateFitScale();
		translateX = 0;
		translateY = 0;
		applyTransform();
	};

	// Set up event listeners
	const zoomInBtn = document.getElementById("zoom-in-btn");
	const zoomOutBtn = document.getElementById("zoom-out-btn");
	const zoomResetBtn = document.getElementById("zoom-reset-btn");

	if (zoomInBtn && zoomOutBtn && zoomResetBtn) {
		zoomInBtn.addEventListener("click", () => zoomInAtPoint());
		zoomOutBtn.addEventListener("click", zoomOut);
		zoomResetBtn.addEventListener("click", resetImageZoom);
	}

	imageContainer.addEventListener("wheel", (e) => {
		e.preventDefault();
		if (e.deltaY < 0) {
			zoomInAtPoint(e.clientX, e.clientY);
		} else {
			zoomOut();
		}
	});

	// Click to zoom in at the clicked point
	modalImage.addEventListener("click", (e) => {
		// Only zoom in on click if image is at its fitted size
		if (currentScale <= calculateFitScale()) {
			zoomInAtPoint(e.clientX, e.clientY);
		}
	});

	// Mouse drag - allow dragging when image is larger than container
	modalImage.addEventListener("mousedown", (e) => {
		// Allow dragging only if the image is larger than its container
		if (currentScale > calculateFitScale()) {
			e.preventDefault();
			isDragging = true;
			startX = e.clientX;
			startY = e.clientY;
			dragStartTranslateX = translateX;
			dragStartTranslateY = translateY;
			modalImage.style.cursor = "grabbing";
		}
	});

	document.addEventListener("mousemove", (e) => {
		if (isDragging) {
			const deltaX = e.clientX - startX;
			const deltaY = e.clientY - startY;
			translateX = dragStartTranslateX + deltaX / currentScale;
			translateY = dragStartTranslateY + deltaY / currentScale;
			applyTransform();
		}
	});

	document.addEventListener("mouseup", () => {
		if (isDragging) {
			isDragging = false;
			updateCursor();
		}
	});

	// Initialize with fit-to-container scale when image loads
	modalImage.addEventListener("load", () => {
		window.resetImageZoom();
	});

	// If image is already loaded from cache
	if (modalImage.complete && modalImage.naturalHeight > 0) {
		window.resetImageZoom();
	}

	updateCursor();
}

function handleImageModalKeydown(e) {
	if (e.key === "Escape") {
		e.preventDefault();
		closeImageModal();
	}
}

// Centralized function to initialize quiz forms
function initializeQuizForms(parentElement) {
	// Find all quiz forms within the provided element (e.g., a new message or the question bank)
	const quizForms = parentElement.querySelectorAll(".quiz-question form");

	quizForms.forEach((form) => {
		// Check if this form has already been initialized to prevent duplicate listeners
		if (form.dataset.initialized) {
			return;
		}
		form.dataset.initialized = "true";

		form.addEventListener("submit", function (event) {
			event.preventDefault(); // Stop the default form submission!

			const questionDiv = form.closest(".quiz-question");
			const selectedOption = form.querySelector("input[type=radio]:checked");
			const feedbackDiv = questionDiv.querySelector(".quiz-feedback");

			if (!selectedOption) {
				feedbackDiv.textContent = "Please select an answer.";
				feedbackDiv.className = "quiz-feedback mt-1.5 text-yellow-400 text-xs";
				return;
			}

			const isCorrect = selectedOption.value === questionDiv.dataset.correct;

			if (isCorrect) {
				feedbackDiv.textContent = "Correct! Well done.";
				feedbackDiv.className = "quiz-feedback mt-1.5 text-green-400 font-bold";
			} else {
				feedbackDiv.textContent = `Not quite. The correct answer is ${questionDiv.dataset.correct}.`;
				feedbackDiv.className = "quiz-feedback mt-1.5 text-red-400";
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

	const savedYoutubeModeState = localStorage.getItem("youtubeModeActive");
	if (savedYoutubeModeState !== null) {
		isYoutubeModeActive = JSON.parse(savedYoutubeModeState);
		console.log("Loaded YouTube mode state:", isYoutubeModeActive);
	} else {
		localStorage.setItem(
			"youtubeModeActive",
			JSON.stringify(isYoutubeModeActive)
		);
	}

	// DOM elements
	const form = document.getElementById("chat-form");
	const textarea = document.getElementById("prompt");
	const stopButton = document.getElementById("stop-button");
	const submitButton = document.getElementById("submit-button"); // Get submit button
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
	const youtubeModeToggleButton = document.getElementById(
		"youtube-mode-toggle"
	);
	const ragModalOverlay = document.getElementById("rag-modal-overlay");

	// Sidebar toggle
	let sidebarOpen = false;

	// Sidebar toggle button
	sidebarToggle.addEventListener("click", (e) => {
		e.stopPropagation();
		console.log("Sidebar toggle clicked");
		if (sidebar.classList.contains("-translate-x-full")) {
			openSidebar();
		} else {
			closeSidebar();
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

		// Adjust study hub button position when sidebar opens
		const hubButtonContainer = document.getElementById("hub-button-container");
		if (hubButtonContainer) {
			hubButtonContainer.classList.remove("left-40");
			hubButtonContainer.classList.add("left-80"); // 320px (256px sidebar + 64px original offset)
		}
	}

	function closeSidebar() {
		sidebarOpen = false;
		sidebar.classList.add("-translate-x-full");
		mainContent.classList.remove("pl-64");

		// Reset study hub button position when sidebar closes
		const hubButtonContainer = document.getElementById("hub-button-container");
		if (hubButtonContainer) {
			hubButtonContainer.classList.remove("left-80");
			hubButtonContainer.classList.add("left-40");
		}
	}

	// Click outside to close - but be more selective
	document.addEventListener("click", (e) => {
		const clickedSidebar = sidebar.contains(e.target);
		const clickedToggle = sidebarToggle.contains(e.target);
		const clickedMainContent = mainContent.contains(e.target);
		const clickedChatInput = document
			.getElementById("chat-form")
			?.contains(e.target);
		const clickedModal = e.target.closest(
			".rag-modal-overlay, #image-modal-overlay, #delete-confirm-dialog"
		);

		// Only close sidebar if:
		// 1. Sidebar is open
		// 2. Not clicking on sidebar itself or toggle button
		// 3. Not clicking on main chat content area
		// 4. Not clicking on chat input form
		// 5. Not clicking on any modal
		if (
			sidebarOpen &&
			!clickedSidebar &&
			!clickedToggle &&
			!clickedMainContent &&
			!clickedChatInput &&
			!clickedModal
		) {
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

	// Typing indicator - simplified to just show animated dots
	window.createTypingIndicator = function () {
		window.removeTypingIndicator(); // Remove any existing indicator

		const typingDiv = document.createElement("div");
		typingDiv.className = "message-enter px-4 md:px-6 py-6";
		typingDiv.id = "typing-indicator";

		typingDiv.innerHTML = `
			<div class="chat-container flex gap-4 md:gap-6">
				<div>
					<div class="w-full flex items-center justify-center text-white">
						<img src="/static/images/logo.png" alt="Assistant icon" class="h-20 w-20">
					</div>
				</div>
				<div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]" data-role="assistant-content-wrapper">
					<div class="typing-dots text-gray-400">
						<span>●</span>
						<span>●</span>
						<span>●</span>
					</div>
				</div>
			</div>
		`;

		document.getElementById("chat-messages").appendChild(typingDiv);
		window.smoothScrollToBottom();
	};

	// Transform typing indicator into response message
	window.transformTypingIndicatorToMessage = function (content, type = "text") {
		const indicator = document.getElementById("typing-indicator");
		if (!indicator) {
			// Fallback: create new message if no typing indicator exists
			return window.appendMessage("assistant", content, null, type);
		}

		// Remove the typing indicator ID and dots
		indicator.removeAttribute("id");
		const contentWrapper = indicator.querySelector(
			'[data-role="assistant-content-wrapper"]'
		);

		if (contentWrapper) {
			// Replace typing dots with actual content
			if (type === "text") {
				const markdownContentHtml = `<div class="max-w-none markdown-content text-gray-100">${marked.parse(
					content
				)}</div>`;
				contentWrapper.innerHTML = markdownContentHtml;

				const markdownContentDiv =
					contentWrapper.querySelector(".markdown-content");
				if (markdownContentDiv) {
					markdownContentDiv.dataset.rawTextBuffer = content;
					if (typeof hljs !== "undefined") {
						markdownContentDiv.querySelectorAll("pre code").forEach((block) => {
							hljs.highlightElement(block);
						});
					}
					initializeCodeBlockFeatures(markdownContentDiv);
					return markdownContentDiv; // Return for streaming updates
				}
			}
		}

		return contentWrapper;
	};

	window.removeTypingIndicator = function () {
		const indicator = document.getElementById("typing-indicator");
		if (indicator) {
			indicator.remove();
		}
	};

	// Smooth scroll - now more intelligent about when to scroll
	window.smoothScrollToBottom = function (force = false) {
		// Check if user is already near the bottom (within 100px)
		const scrollPosition =
			window.pageYOffset || document.documentElement.scrollTop;
		const windowHeight = window.innerHeight;
		const documentHeight = document.documentElement.scrollHeight;
		const distanceFromBottom = documentHeight - (scrollPosition + windowHeight);

		// Only auto-scroll if user is near the bottom or if forced
		if (force || distanceFromBottom <= 100) {
			window.scrollTo({
				top: document.body.scrollHeight,
				behavior: "smooth"
			});
		}
	};

	// Function to check if user is near bottom (for conditional scrolling)
	window.isNearBottom = function (threshold = 100) {
		const scrollPosition =
			window.pageYOffset || document.documentElement.scrollTop;
		const windowHeight = window.innerHeight;
		const documentHeight = document.documentElement.scrollHeight;
		const distanceFromBottom = documentHeight - (scrollPosition + windowHeight);
		return distanceFromBottom <= threshold;
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

	// Helper function to create assistant message structure
	function createAssistantMessageStructure(contentHtml) {
		return `
			<div class="chat-container flex gap-4 md:gap-6">
				<div>
					<div class="w-full flex items-center justify-center text-white">
						<img src="/static/images/logo.png" alt="Assistant icon" class="h-20 w-20">
					</div>
				</div>
				<div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]" data-role="assistant-content-wrapper">
					${contentHtml}
				</div>
			</div>
		`;
	}

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

		// Remove empty placeholder if present
		const placeholder = document.getElementById("initial-chat-placeholder");
		if (placeholder) placeholder.remove();

		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		let contentElementToReturn = messageDiv; // Default to outer div

		if (role === "user") {
			// User message - right aligned
			messageDiv.innerHTML = `
				<div class="chat-container flex flex-row-reverse gap-4 md:gap-6 justify-start">
					<!-- User icon - right side -->
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
			let assistantContentHtml = "";
			if (type === "quiz") {
				if (content) {
					assistantContentHtml += `<div class="max-w-none markdown-content text-gray-100">${marked.parse(
						content
					)}</div>`;
				}
				if (quizHtml) {
					assistantContentHtml += `<div class="quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl mt-2">${quizHtml}</div>`;
				}
			} else if (type === "diagram") {
				assistantContentHtml = `
					<div class="diagram-message-container bg-gray-800/50 p-2 my-2 rounded-lg shadow-md flex flex-col justify-center items-center">
						<img src="${content}" alt="Generated Diagram" class="max-w-full h-auto rounded-md mb-1 cursor-pointer hover:opacity-90 transition-opacity" onclick="openImageModal('${content}')">
						${
							messageId
								? `<p class="text-xs text-gray-400 italic mt-1 text-center">${messageId}</p>`
								: ""
						}
					</div>`;
			} else {
				assistantContentHtml = `<div class="max-w-none markdown-content text-gray-100">${marked.parse(
					content
				)}</div>`;
			}

			messageDiv.innerHTML =
				createAssistantMessageStructure(assistantContentHtml);

			if (type === "text") {
				// For assistant text messages, we want to return the actual content div for streaming updates
				const markdownContentDiv =
					messageDiv.querySelector(".markdown-content");
				if (markdownContentDiv) {
					contentElementToReturn = markdownContentDiv;
					// Initialize raw text buffer for streaming
					markdownContentDiv.dataset.rawTextBuffer = content;
					// Initial parse is already done when setting assistantContentHtml
					if (typeof hljs !== "undefined") {
						markdownContentDiv.querySelectorAll("pre code").forEach((block) => {
							hljs.highlightElement(block);
						});
					}
					initializeCodeBlockFeatures(markdownContentDiv);
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

	function renderAndAppendQuiz(quizData) {
		const messagesDiv = document.getElementById("chat-messages");

		// Remove empty placeholder if present
		const placeholder = document.getElementById("initial-chat-placeholder");
		if (placeholder) placeholder.remove();

		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		if (quizData.message_id) {
			messageDiv.dataset.messageId = quizData.message_id;
		}

		let assistantContentHtml = "";
		if (quizData.content) {
			assistantContentHtml += `<div class="max-w-none markdown-content text-gray-100">${marked.parse(
				quizData.content
			)}</div>`;
		}
		if (quizData.quiz_html) {
			assistantContentHtml += `<div class="quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl mt-2">${quizData.quiz_html}</div>`;
		}

		messageDiv.innerHTML =
			createAssistantMessageStructure(assistantContentHtml);

		messagesDiv.appendChild(messageDiv);

		// Process the quiz content that was just added
		const quizMessageElement = messageDiv.querySelector(".quiz-message");
		if (quizMessageElement) {
			unwrapQuizMessageCodeBlocks(quizMessageElement);
			fixEscapedQuizMessages(quizMessageElement);
			fixFirstLineQuizPreCode(quizMessageElement);
			initializeQuizForms(quizMessageElement);
		}

		window.smoothScrollToBottom();
	}

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

	function simulateTypingByCharacter(text, container) {
		if (!container || !text) {
			// If there's no text, ensure the typing indicator is gone.
			const indicator = document.getElementById("typing-indicator");
			if (indicator) indicator.remove();
			return;
		}
		let charIndex = 0;

		// Ensure container is empty before starting and has a buffer for parsing later
		container.textContent = "";
		if (container.dataset) {
			container.dataset.rawTextBuffer = text;
		}

		function showNextCharacter() {
			if (charIndex < text.length) {
				container.textContent += text.charAt(charIndex);
				charIndex++;
				window.smoothScrollToBottom(true); // Force scroll
				// Use a short delay for a fast, smooth typing effect
				setTimeout(showNextCharacter, 2);
			} else {
				// Typing finished, parse the whole thing as markdown
				if (typeof marked !== "undefined") {
					const finalContent =
						container.dataset.rawTextBuffer || container.textContent;
					container.innerHTML = marked.parse(finalContent);
					if (typeof hljs !== "undefined") {
						container.querySelectorAll("pre code").forEach((block) => {
							hljs.highlightElement(block);
						});
					}
					initializeCodeBlockFeatures(container);
				}
			}
		}
		showNextCharacter();
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
			}
			// The text content is now handled by the `simulateTypingByCharacter` function,
			// so the logic for .markdown-content has been removed from here.
		}
	}

	window.handleStreamResponse = async function (response) {
		const reader = response.body.getReader();
		const decoder = new TextDecoder();
		let buffer = "";
		let currentMessageContainer = null; // This will hold the .markdown-content div for the current assistant message
		let isFirstTextChunk = true;
		let accumulatedText = ""; // Accumulate all text content here
		let isMixedContentMessage = false; // Track if we're building a mixed content message
		let mixedContentElements = []; // Store elements for mixed content with order info
		let toolResultCount = 0; // Track how many tool results we've received
		let streamFinished = false; // Flag to indicate server has sent the 'done' message
		let streamTimeout;

		function resetTimeout() {
			clearTimeout(streamTimeout);
			streamTimeout = setTimeout(() => {
				console.warn("Stream timeout reached. Forcing termination.");
				streamFinished = true;
			}, 2000); // 2-second timeout
		}

		try {
			while (true) {
				resetTimeout(); // Reset timeout with each new data chunk
				const { value, done } = await reader.read();
				if (done) break;

				buffer += decoder.decode(value, { stream: true });
				const lines = buffer.split("\n");
				buffer = lines.pop() || "";

				for (const line of lines) {
					if (line.startsWith("data: ")) {
						const data = JSON.parse(line.slice(6));

						if (data.type === "trigger_quiz_render") {
							const messageId = data.message_id;
							if (messageId) {
								fetch(`/chat/quiz_html/${messageId}/`)
									.then((response) => response.json())
									.then((quizData) => {
										if (quizData.quiz_html) {
											renderAndAppendQuiz(quizData);
										}
									})
									.catch((error) => {
										console.error(
											"Error fetching agent-generated quiz:",
											error
										);
										appendSystemNotification(
											`Error rendering quiz: ${error.message}`,
											"error"
										);
									});
							}
							isFirstTextChunk = true;
							currentMessageContainer = null;
							toolResultCount = 0;
						} else if (data.type === "quiz") {
							// A quiz is a self-contained message. Transform the typing indicator.
							window.removeTypingIndicator(); // Remove typing indicator first
							window.appendMessage(
								"assistant",
								data.content || "Here is your quiz:", // Fallback content
								data.message_id,
								"quiz",
								data.quiz_html
							);
							// Reset streaming state for any subsequent messages in this response
							currentMessageContainer = null;
							isFirstTextChunk = true;
							toolResultCount = 0;
						} else if (data.type === "quiz_html") {
							toolResultCount++;
							// Auto-detect mixed content if we have other elements or text content
							if (
								!isMixedContentMessage &&
								(mixedContentElements.length > 0 || currentMessageContainer)
							) {
								isMixedContentMessage = true;
							}

							if (isMixedContentMessage) {
								const quizElement = createQuizElement(data.quiz_html);
								// Store order information for proper sorting
								quizElement.dataset.order = data.order || toolResultCount;
								mixedContentElements.push({
									element: quizElement,
									order: parseInt(data.order) || toolResultCount,
									type: "quiz"
								});
								console.log(
									`Added quiz to mixed content with order: ${
										data.order || toolResultCount
									}`
								);
							} else {
								// Standalone quiz - remove typing indicator first
								window.removeTypingIndicator();
								renderAndAppendQuiz({ quiz_html: data.quiz_html });
							}
						} else if (data.type === "mixed_content_start") {
							// Signal that we're starting a mixed content message
							isMixedContentMessage = true;
							mixedContentElements = [];
							toolResultCount = 0;
						} else if (data.type === "content") {
							// Check if we should enter mixed content mode based on previous elements
							if (!isMixedContentMessage && mixedContentElements.length > 0) {
								isMixedContentMessage = true;
							}

							if (isFirstTextChunk) {
								// Transform the typing indicator into an empty message container
								currentMessageContainer =
									window.transformTypingIndicatorToMessage("", "text");
								isFirstTextChunk = false;
							}
							// Don't update the DOM, just collect the text
							accumulatedText += data.content;
						} else if (data.type === "error") {
							appendSystemNotification(data.content, "error");
						} else if (data.type === "diagram_image") {
							toolResultCount++;
							// Handle diagram image data
							console.log("Received diagram image data:", data);
							if (data.diagram_image_id) {
								const imageUrl = `/chat/diagram_image/${data.diagram_image_id}/`; // Construct URL

								// Auto-detect mixed content if we have other elements or text content
								if (
									!isMixedContentMessage &&
									(mixedContentElements.length > 0 || currentMessageContainer)
								) {
									isMixedContentMessage = true;
								}

								if (isMixedContentMessage) {
									// Add to mixed content elements with order information
									const diagramElement = createDiagramElement(
										imageUrl,
										data.text_content || "Generated Diagram"
									);
									// Store order information for proper sorting
									diagramElement.dataset.order = data.order || toolResultCount;
									mixedContentElements.push({
										element: diagramElement,
										order: parseInt(data.order) || toolResultCount,
										type: "diagram"
									});
									console.log(
										`Added diagram to mixed content with order: ${
											data.order || toolResultCount
										}`
									);
								} else {
									// Standalone diagram - remove typing indicator first
									window.removeTypingIndicator();
									appendDiagramMessage(
										imageUrl,
										data.text_content || "Generated Diagram",
										data.message_id
									);
									// After a diagram is handled, reset state for the next message component
									currentMessageContainer = null;
									isFirstTextChunk = true;
								}
							} else {
								appendSystemNotification(
									"Error: Received diagram response without diagram_image_id",
									"error"
								);
							}
						} else if (data.type === "done") {
							// If we have mixed content elements OR multiple tool results, combine them into a single message
							if (
								(isMixedContentMessage && mixedContentElements.length > 0) ||
								toolResultCount > 1
							) {
								createMixedContentMessage(
									mixedContentElements,
									currentMessageContainer
								);
								// Reset state
								isMixedContentMessage = false;
								mixedContentElements = [];
								currentMessageContainer = null;
								isFirstTextChunk = true;
								toolResultCount = 0;
							}
							// Do not remove typing indicator here, it's handled in the finally block
							streamFinished = true; // Set flag to terminate the stream
						} else if (data.type === "youtube_recommendations") {
							toolResultCount++;
							// Auto-detect mixed content if we have other elements or text content
							if (
								!isMixedContentMessage &&
								(mixedContentElements.length > 0 || currentMessageContainer)
							) {
								isMixedContentMessage = true;
							}

							if (isMixedContentMessage) {
								// Add to mixed content elements with order information
								const youtubeElement = createYoutubeElement(data.data);
								// Store order information for proper sorting
								youtubeElement.dataset.order = data.order || toolResultCount;
								mixedContentElements.push({
									element: youtubeElement,
									order: parseInt(data.order) || toolResultCount,
									type: "youtube"
								});
								console.log(
									`Added YouTube to mixed content with order: ${
										data.order || toolResultCount
									}`
								);
							} else {
								// Standalone YouTube recommendations - remove typing indicator first
								window.removeTypingIndicator();
								const messagesContainer =
									document.getElementById("chat-messages");

								// Remove empty placeholder if present
								const placeholder = document.getElementById(
									"initial-chat-placeholder"
								);
								if (placeholder) placeholder.remove();

								const messageDiv = document.createElement("div");
								messageDiv.className = "message-enter px-4 md:px-6 py-6";

								messageDiv.innerHTML = createAssistantMessageStructure(`
									<div data-role="youtube-content-wrapper">
										<!-- YouTube recommendations will be rendered here -->
									</div>
								`);
								messagesContainer.appendChild(messageDiv);
								const youtubeWrapper = messageDiv.querySelector(
									'[data-role="youtube-content-wrapper"]'
								);

								if (window.YoutubeHandler && youtubeWrapper) {
									window.YoutubeHandler.renderRecommendations(
										youtubeWrapper,
										data.data
									);
								}
								// Reset streaming state
								currentMessageContainer = null;
								isFirstTextChunk = true;
							}
						}
					}
				}

				if (streamFinished) {
					console.log(
						"Done message received from server, breaking client-side loop."
					);
					break; // Exit the while(true) loop
				}
			}
		} catch (error) {
			console.error("Error in handleStreamResponse:", error);
			window.removeTypingIndicator();
		} finally {
			clearTimeout(streamTimeout);
			if (currentMessageContainer && accumulatedText) {
				// Start the fake typing animation with the fully collected text
				simulateTypingByCharacter(accumulatedText, currentMessageContainer);
			} else {
				// If no text was received, ensure the typing indicator is removed.
				window.removeTypingIndicator();
			}
		}
	};

	// Removed duplicate appendUserMessage - using window.appendMessage("user", content) instead

	form.addEventListener("submit", async function (e) {
		e.preventDefault();
		let promptText = textarea.value.trim();
		const fileData = fileInput.files[0];
		const imageData = document.getElementById("image-upload").files[0];

		if (fileData) {
			promptText = promptText
				? `${promptText}\n\n[Attached file: ${fileData.name}]`
				: `[Attached file: ${fileData.name}]`;
		}

		if (imageData) {
			promptText = promptText
				? `${promptText}\n\n[Attached image: ${imageData.name}]`
				: `[Attached image: ${imageData.name}]`;
		}

		if (!promptText && !fileData && !imageData) return;

		// --- Start of UI state change ---
		window.appendMessage("user", promptText);
		textarea.value = "";
		window.adjustMainTextareaHeight();
		if (fileData) clearFileSelection();
		if (imageData && window.clearImageSelection) window.clearImageSelection();
		window.createTypingIndicator();

		// Swap send button for stop button
		submitButton.classList.add("hidden");
		stopButton.classList.remove("hidden");
		abortController = new AbortController();
		// --- End of UI state change ---

		try {
			const formData = new FormData();
			formData.append("prompt", promptText);
			formData.append(
				"csrfmiddlewaretoken",
				document.querySelector("[name=csrfmiddlewaretoken]").value
			);
			if (fileData) formData.append("file", fileData);
			if (imageData) formData.append("image_file", imageData);

			console.log("Submitting form with states:", {
				isRAGActive,
				isDiagramModeActive,
				isYoutubeModeActive
			});

			formData.append("rag_mode_active", isRAGActive.toString());
			formData.append("diagram_mode_active", isDiagramModeActive.toString());
			formData.append("youtube_mode_active", isYoutubeModeActive.toString());

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

				// Remove "No chats yet" message if it exists
				const noChatMessage = chatsList.querySelector("p");
				if (
					noChatMessage &&
					noChatMessage.textContent.includes("No chats yet")
				) {
					noChatMessage.remove();
				}

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
			if (error.name === "AbortError") {
				// User clicked stop, show the message
				appendMessage("assistant", `_Response stopped by user._`);
			} else {
				// Other errors
				window.appendMessage(
					"assistant",
					`Error: ${error.message}`,
					null,
					"text"
				);
			}
		} finally {
			// Restore the button states regardless of outcome
			console.log(
				"Executing submit handler's finally block. Hiding stop button."
			);
			stopButton.classList.add("hidden");
			submitButton.classList.remove("hidden");
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
			// The catch/finally block in the submit handler will now manage UI changes
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
					<div id="initial-chat-placeholder" class="flex flex-col items-center justify-center h-[calc(100vh-200px)]">
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

					// Keep sidebar open after deletion
					// No need to close sidebar here
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

	// Clean up any legacy message styling

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

	// Quiz and code block features are now handled directly in appendMessage

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
	const MAX_RAG_FILES = 10;

	function updateRagToggleButtonStyle(isActive) {
		if (!ragToggleButton) return;
		console.log(
			`Setting RAG button style to: ${isActive ? "ACTIVE" : "INACTIVE"}`
		);
		const icon = ragToggleButton.querySelector("svg");
		const text = ragToggleButton.querySelector("span");

		if (isActive) {
			ragToggleButton.classList.add("bg-gray-800");
			if (icon) {
				icon.classList.remove("text-gray-400");
				icon.classList.add("text-green-400");
			}
			if (text) {
				text.classList.remove("text-gray-400");
				text.classList.add("text-green-400");
			}
		} else {
			ragToggleButton.classList.remove("bg-gray-800");
			if (icon) {
				icon.classList.remove("text-green-400");
				icon.classList.add("text-gray-400");
			}
			if (text) {
				text.classList.remove("text-green-400");
				text.classList.add("text-gray-400");
			}
		}
	}

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

		// Initial styling based on loaded/default state
		updateRagToggleButtonStyle(isRAGActive);

		ragToggleButton.addEventListener("click", () => {
			console.log("RAG button clicked, current state:", isRAGActive);
			isRAGActive = !isRAGActive;
			console.log("Toggling RAG mode to:", isRAGActive);

			updateRagToggleButtonStyle(isRAGActive);

			if (isRAGActive) {
				// If RAG becomes active, disable other modes
				if (isDiagramModeActive) {
					isDiagramModeActive = false;
					updateDiagramModeToggleButtonStyle();
					localStorage.setItem(
						"diagramModeActive",
						JSON.stringify(isDiagramModeActive)
					);
				}
				if (isYoutubeModeActive) {
					isYoutubeModeActive = false;
					updateYoutubeModeToggleButton();
					localStorage.setItem(
						"youtubeModeActive",
						JSON.stringify(isYoutubeModeActive)
					);
				}
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
		const icon = diagramModeToggleButton.querySelector("svg");
		const text = diagramModeToggleButton.querySelector("span");
		if (isDiagramModeActive) {
			console.log("Setting diagram mode active styles");
			diagramModeToggleButton.classList.add("bg-gray-800"); // Add background for better visual feedback
			if (icon) {
				icon.classList.remove("text-gray-400");
				icon.classList.add("text-blue-400");
			}
			if (text) {
				text.classList.remove("text-gray-400");
				text.classList.add("text-blue-400");
			}
		} else {
			console.log("Setting diagram mode inactive styles");
			diagramModeToggleButton.classList.remove("bg-gray-800"); // Remove background
			if (icon) {
				icon.classList.remove("text-blue-400");
				icon.classList.add("text-gray-400");
			}
			if (text) {
				text.classList.remove("text-blue-400");
				text.classList.add("text-gray-400");
			}
		}
	}

	if (diagramModeToggleButton) {
		console.log("Found diagram mode toggle button", isDiagramModeActive);

		updateDiagramModeToggleButtonStyle(); // Set initial style

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
					updateRagToggleButtonStyle(false); // Use the RAG inactive style function
					localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
				}
				if (isYoutubeModeActive) {
					isYoutubeModeActive = false;
					updateYoutubeModeToggleButton();
					localStorage.setItem(
						"youtubeModeActive",
						JSON.stringify(isYoutubeModeActive)
					);
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

	// YouTube Mode Toggle Button Logic
	function updateYoutubeModeToggleButton() {
		if (!youtubeModeToggleButton) return;
		const icon = youtubeModeToggleButton.querySelector("svg");
		const text = youtubeModeToggleButton.querySelector("span");
		if (isYoutubeModeActive) {
			console.log("Setting youtube mode active styles");
			youtubeModeToggleButton.classList.add("bg-gray-800");
			if (icon) {
				icon.classList.remove("text-gray-400");
				icon.classList.add("text-red-500");
			}
			if (text) {
				text.classList.remove("text-gray-400");
				text.classList.add("text-red-500");
			}
		} else {
			console.log("Setting youtube mode inactive styles");
			youtubeModeToggleButton.classList.remove("bg-gray-800");
			if (icon) {
				icon.classList.remove("text-red-500");
				icon.classList.add("text-gray-400");
			}
			if (text) {
				text.classList.remove("text-red-500");
				text.classList.add("text-gray-400");
			}
		}
	}

	if (youtubeModeToggleButton) {
		console.log("Found YouTube mode toggle button", isYoutubeModeActive);
		updateYoutubeModeToggleButton();

		youtubeModeToggleButton.addEventListener("click", () => {
			console.log(
				"YouTube mode button clicked, current state:",
				isYoutubeModeActive
			);
			isYoutubeModeActive = !isYoutubeModeActive;
			console.log("Toggling YouTube mode to:", isYoutubeModeActive);

			updateYoutubeModeToggleButton();
			if (isYoutubeModeActive) {
				if (isRAGActive) {
					isRAGActive = false;
					updateRagToggleButtonStyle(false);
					localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
				}
				if (isDiagramModeActive) {
					isDiagramModeActive = false;
					updateDiagramModeToggleButtonStyle();
					localStorage.setItem(
						"diagramModeActive",
						JSON.stringify(isDiagramModeActive)
					);
				}
			}
			localStorage.setItem(
				"youtubeModeActive",
				JSON.stringify(isYoutubeModeActive)
			);
			appendSystemNotification(
				`YouTube mode is now ${isYoutubeModeActive ? "ACTIVE" : "INACTIVE"}.`,
				"info"
			);
		});
	} else {
		console.warn("YouTube mode toggle button not found in the DOM");
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
		const placeholder = document.getElementById("initial-chat-placeholder");
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

		const diagramContentHtml = `
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
		`;

		messageDiv.innerHTML = createAssistantMessageStructure(diagramContentHtml);

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
							renderAndAppendQuiz(data);
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

	window.YoutubeHandler = {
		renderRecommendations: function (container, videoData) {
			if (!Array.isArray(videoData) || videoData.length === 0) {
				return;
			}

			// Create a container for the recommendations
			const recommendationsContainer = document.createElement("div");
			recommendationsContainer.className =
				"youtube-recommendations-container space-y-3";

			// Add a header text
			const header = document.createElement("p");
			header.className = "text-gray-200";
			header.textContent = "Here are some videos I found for you:";
			recommendationsContainer.appendChild(header);

			// Create and append each video embed
			videoData.forEach((video) => {
				const link = document.createElement("a");
				link.href = video.url;
				link.target = "_blank";
				link.rel = "noopener noreferrer";
				link.className =
					"flex items-center bg-gray-800/50 hover:bg-gray-700/60 border border-gray-700 rounded-lg p-2 no-underline transition-all duration-200 group";

				const thumbnailDiv = document.createElement("div");
				thumbnailDiv.className = "flex-shrink-0 w-32 h-18 mr-3";

				const thumbnailImg = document.createElement("img");
				thumbnailImg.src = video.thumbnail;
				thumbnailImg.alt = `Thumbnail for ${video.title}`;
				thumbnailImg.className =
					"w-full h-full object-cover rounded-md border border-gray-600";

				thumbnailDiv.appendChild(thumbnailImg);

				const infoDiv = document.createElement("div");
				infoDiv.className = "flex-1 min-w-0";

				const titleP = document.createElement("p");
				titleP.className =
					"text-gray-100 font-medium text-sm truncate group-hover:text-white";
				titleP.textContent = video.title;

				infoDiv.appendChild(titleP);

				link.appendChild(thumbnailDiv);
				link.appendChild(infoDiv);

				recommendationsContainer.appendChild(link);
			});

			container.appendChild(recommendationsContainer);
		}
	};

	// Helper functions for mixed content messages
	function createDiagramElement(imageUrl, textContent) {
		const diagramDiv = document.createElement("div");
		diagramDiv.className = "diagram-component mb-4";
		diagramDiv.innerHTML = `
			<div class="diagram-content">
				<p class="text-sm text-gray-600 mb-2">${textContent}</p>
				<div class="diagram-image-container">
					<img src="${imageUrl}" alt="Generated Diagram" 
						 class="diagram-image cursor-pointer max-w-full h-auto rounded-lg shadow-lg"
						 onclick="openImageModal('${imageUrl}')">
				</div>
			</div>
		`;
		return diagramDiv;
	}

	function createYoutubeElement(videos) {
		const youtubeDiv = document.createElement("div");
		youtubeDiv.className = "youtube-component mb-4";
		youtubeDiv.innerHTML =
			'<div class="youtube-content" data-role="youtube-content-wrapper"></div>';

		const youtubeWrapper = youtubeDiv.querySelector(
			'[data-role="youtube-content-wrapper"]'
		);
		if (window.YoutubeHandler && youtubeWrapper) {
			window.YoutubeHandler.renderRecommendations(youtubeWrapper, videos);
		}

		return youtubeDiv;
	}

	function createQuizElement(quizHtml) {
		const quizDiv = document.createElement("div");
		quizDiv.className =
			"quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl";
		quizDiv.innerHTML = `
			<div class="quiz-content">
				<div class="quiz-message">${quizHtml}</div>
			</div>
		`;

		// Apply quiz fixes and initialize forms
		const quizMessage = quizDiv.querySelector(".quiz-message");
		if (quizMessage) {
			unwrapQuizMessageCodeBlocks(quizMessage);
			fixEscapedQuizMessages(quizMessage);
			fixFirstLineQuizPreCode(quizMessage);
			initializeQuizForms(quizMessage);
		}

		return quizDiv;
	}

	function createMixedContentMessage(mixedElements, textContainer) {
		const messagesContainer = document.getElementById("chat-messages");

		// Remove empty placeholder if present
		const placeholder = document.getElementById("initial-chat-placeholder");
		if (placeholder) placeholder.remove();

		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";

		messageDiv.innerHTML = createAssistantMessageStructure(`
			<div data-role="mixed-content-wrapper">
				<!-- Mixed content will be rendered here -->
			</div>
		`);

		const contentWrapper = messageDiv.querySelector(
			'[data-role="mixed-content-wrapper"]'
		);

		// Add text content first if it exists
		if (
			textContainer &&
			textContainer.dataset &&
			textContainer.dataset.rawTextBuffer
		) {
			const textDiv = document.createElement("div");
			textDiv.className = "text-component markdown-content mb-4";

			// Copy the processed content from the text container
			if (typeof marked !== "undefined" && typeof hljs !== "undefined") {
				marked.setOptions({
					breaks: false,
					gfm: true
				});
				const parsedHtml = marked.parse(textContainer.dataset.rawTextBuffer);
				textDiv.innerHTML = parsedHtml;

				// Re-apply syntax highlighting
				textDiv.querySelectorAll("pre code").forEach((block) => {
					hljs.highlightElement(block);
				});
				initializeCodeBlockFeatures(textDiv);
			} else {
				textDiv.textContent = textContainer.dataset.rawTextBuffer;
			}

			contentWrapper.appendChild(textDiv);
		}

		// Sort mixed content elements by order before adding them
		if (Array.isArray(mixedElements) && mixedElements.length > 0) {
			// Check if elements have the new structure with order info
			if (
				mixedElements[0] &&
				typeof mixedElements[0] === "object" &&
				mixedElements[0].element
			) {
				// New structure: sort by order and extract elements
				console.log("Sorting mixed content elements by requested order...");
				const sortedElements = mixedElements
					.sort((a, b) => (a.order || 0) - (b.order || 0))
					.map((item) => {
						console.log(
							`Placing ${item.type} element with order: ${item.order}`
						);
						return item.element;
					});

				// Add sorted elements to content wrapper
				sortedElements.forEach((element) => {
					contentWrapper.appendChild(element);
				});
			} else {
				// Legacy structure: elements are direct DOM elements
				console.log("Using legacy mixed content structure (no ordering)");
				mixedElements.forEach((element) => {
					contentWrapper.appendChild(element);
				});
			}
		}

		messagesContainer.appendChild(messageDiv);
		applyConsistentChatElementStyling(messageDiv);
		window.smoothScrollToBottom();

		// Remove the temporary text container if it exists
		if (textContainer && textContainer.parentNode) {
			textContainer.parentNode.parentNode.remove();
		}
	}

	// Initialize image upload functionality
	initializeImageUpload();

	// Removed duplicate appendUserMessage function - using window.appendMessage("user", content) instead
});

function updateNewChatUI(isNew) {
	const quizButtonContainer = document.getElementById("quiz-button-container");
	const manageRagButton = document.getElementById("manage-rag-context-btn");
	const hubButtonContainer = document.getElementById("hub-button-container");
	const studyHubLink = document.getElementById("study-hub-link");

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
			if (hubButtonContainer) {
				hubButtonContainer.classList.remove("hidden");
				hubButtonContainer.style.display = "";
			}
			if (studyHubLink) {
				studyHubLink.setAttribute(
					"href",
					`/chat/${window.currentChatId}/study/`
				);
			}
			console.log("[updateNewChatUI from chat.js - setTimeout] Buttons shown.");
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

// Image upload functionality
function initializeImageUpload() {
	const imageUploadInput = document.getElementById("image-upload");
	const imagePreviewContainer = document.getElementById(
		"image-preview-container"
	);
	const imagePreview = document.getElementById("image-preview");
	const removeImageBtn = document.getElementById("remove-image-btn");

	if (
		!imageUploadInput ||
		!imagePreviewContainer ||
		!imagePreview ||
		!removeImageBtn
	) {
		console.warn("Image upload elements not found");
		return;
	}

	// Handle image file selection
	imageUploadInput.addEventListener("change", function (e) {
		const file = e.target.files[0];
		if (file) {
			// Validate file type
			const allowedTypes = [
				"image/jpeg",
				"image/png",
				"image/gif",
				"image/webp"
			];
			if (!allowedTypes.includes(file.type)) {
				alert("Please select a valid image file (JPEG, PNG, GIF, or WebP)");
				imageUploadInput.value = "";
				return;
			}

			// Validate file size (max 10MB)
			const maxSize = 10 * 1024 * 1024; // 10MB
			if (file.size > maxSize) {
				alert("Image file is too large. Please select an image under 10MB.");
				imageUploadInput.value = "";
				return;
			}

			// Create preview URL
			const reader = new FileReader();
			reader.onload = function (e) {
				imagePreview.src = e.target.result;
				imagePreviewContainer.classList.remove("hidden");
				imagePreviewContainer.classList.add("flex");
			};
			reader.readAsDataURL(file);
		}
	});

	// Handle image removal
	removeImageBtn.addEventListener("click", function () {
		clearImageSelection();
	});

	function clearImageSelection() {
		imageUploadInput.value = "";
		imagePreview.src = "#";
		imagePreviewContainer.classList.add("hidden");
		imagePreviewContainer.classList.remove("flex");
	}

	// Make clearImageSelection available globally for use in form submission
	window.clearImageSelection = clearImageSelection;
}

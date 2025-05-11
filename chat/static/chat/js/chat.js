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
let isRAGActive = true; // Default if nothing in localStorage

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

// Wrap all logic in DOMContentLoaded
document.addEventListener("DOMContentLoaded", function () {
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
	const ragToggleButton = document.getElementById("rag-toggle-button");

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
	function createTypingIndicator() {
		removeTypingIndicator();

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
		smoothScrollToBottom();
	}

	function removeTypingIndicator() {
		const typingIndicator = document.getElementById("typing-indicator");
		if (typingIndicator) {
			typingIndicator.remove();
		}
	}

	// Smooth scroll
	function smoothScrollToBottom() {
		window.scrollTo({
			top: document.body.scrollHeight,
			behavior: "smooth"
		});
	}

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
	function appendMessage(role, content) {
		const messagesDiv = document.getElementById("chat-messages");

		// Remove empty placeholder if present
		const placeholder = messagesDiv.querySelector(
			".flex.flex-col.items-center.justify-center"
		);
		if (placeholder) placeholder.remove();

		const messageDiv = document.createElement("div");
		messageDiv.className = `message-enter px-4 md:px-6 py-6`;

		let iconHtml = "";
		let contentWrapperClass = "";
		let actualContentHtml = "";
		let mainContainerClass = "chat-container flex gap-4 md:gap-6";

		if (role === "user") {
			mainContainerClass =
				"chat-container flex flex-row-reverse gap-4 md:gap-6 justify-start";
			iconHtml = `<div class="w-7 h-7 rounded-sm bg-[#5436DA] flex items-center justify-center text-white text-xs font-semibold">U</div>`;
			contentWrapperClass = "overflow-x-auto max-w-[75%]";
			actualContentHtml = `<div class="user-message text-gray-100 bg-[#444654] p-3 rounded-lg"><p class="whitespace-pre-wrap">${content}</p></div>`;
		} else {
			// Assistant
			iconHtml = `<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white">
								<img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7">
							</div>`;
			contentWrapperClass = "flex-1 overflow-x-auto min-w-0 max-w-[85%]";
			if (
				content.includes('<div class="quiz-question"') ||
				content.includes('<div class="quiz-message"')
			) {
				actualContentHtml = `<div class="quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl">${content}</div>`;
			} else {
				// For normal assistant messages, create an empty div, content will be set later by textContent
				actualContentHtml = `<div class="max-w-none markdown-content text-gray-100"></div>`;
			}
		}

		messageDiv.innerHTML = `
			<div class="${mainContainerClass}">
				<div class="flex-shrink-0 w-7 h-7">
					${iconHtml}
				</div>
				<div class="${contentWrapperClass}">
					${actualContentHtml}
				</div>
			</div>
		`;

		messagesDiv.appendChild(messageDiv);

		// If assistant and content is NOT quiz, set textContent for later parsing by marked.js
		if (role === "assistant") {
			if (
				!(
					content.includes('<div class="quiz-question"') ||
					content.includes('<div class="quiz-message"')
				)
			) {
				const markdownContainer = messageDiv.querySelector(".markdown-content");
				if (markdownContainer) {
					markdownContainer.textContent = content;
				}
			}
		}

		smoothScrollToBottom();
		// Return the div where content (text or HTML) is placed.
		if (role === "assistant") {
			return messageDiv.querySelector(".markdown-content, .quiz-message");
		}
		return null; // For user messages, not typically needed by caller
	}

	// New function to append system notifications
	function appendSystemNotification(message, level = "info") {
		const messagesDiv = document.getElementById("chat-messages");
		const notificationDiv = document.createElement("div");
		notificationDiv.className = `message-enter px-4 md:px-6 py-3`; // Less padding than full messages

		let bgColor = "bg-gray-700/70"; // Default info
		let textColor = "text-gray-300";
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
		messagesDiv.appendChild(notificationDiv);
		smoothScrollToBottom();
	}

	function updateAssistantMessage(container, content) {
		if (container) {
			if (
				content.includes('<div class="quiz-question"') ||
				content.includes('<div class="quiz-message"')
			) {
				container.innerHTML = content;
			} else {
				container.textContent = content;
			}
			smoothScrollToBottom();
		}
	}

	async function handleStreamResponse(response) {
		if (!response.ok) throw new Error("Failed to get response");
		removeTypingIndicator();

		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		messageDiv.innerHTML = `
			<div class="chat-container flex gap-4 md:gap-6">
				<div class="flex-shrink-0 w-7 h-7">
					<div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white">
						<img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7">
					</div>
				</div>
				<div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]">
					<div class="max-w-none markdown-content text-gray-100"></div>
				</div>
			</div>
		`;

		document.getElementById("chat-messages").appendChild(messageDiv);
		const markdownContainer = messageDiv.querySelector(".markdown-content");
		let assistantMessage = "";

		try {
			const reader = response.body.getReader();
			const decoder = new TextDecoder();

			while (true) {
				const { done, value } = await reader.read();
				if (done) break;

				const chunk = decoder.decode(value);
				const lines = chunk.split("\n\n");

				for (const line of lines) {
					if (line.startsWith("data: ")) {
						try {
							const data = JSON.parse(line.slice(6));

							switch (data.type) {
								case "content":
									assistantMessage += data.content;
									markdownContainer.innerHTML = marked.parse(assistantMessage);
									markdownContainer
										.querySelectorAll("pre code")
										.forEach((block) => {
											if (!block.classList.contains("hljs")) {
												hljs.highlightElement(block);
											}
										});
									if (typeof initializeCodeBlockFeatures === "function") {
										initializeCodeBlockFeatures(markdownContainer);
									}
									smoothScrollToBottom();
									break;

								case "file_info": // Handle new SSE event type
									if (data.status === "truncated" && data.message) {
										appendSystemNotification(data.message, "warning");
									}
									break;

								case "error":
									markdownContainer.innerHTML = `<div class="text-red-400">Error: ${data.content}</div>`;
									break;

								case "done":
									// Final formatting pass
									markdownContainer.innerHTML = marked.parse(assistantMessage);
									markdownContainer
										.querySelectorAll("pre code")
										.forEach((block) => {
											hljs.highlightElement(block);
										});
									if (typeof initializeCodeBlockFeatures === "function") {
										initializeCodeBlockFeatures(markdownContainer);
									}
									break;
							}
						} catch (e) {
							console.error("Failed to parse streaming data:", e);
						}
					}
				}
			}
		} catch (error) {
			if (error.name !== "AbortError") {
				console.error("Stream error:", error);
				markdownContainer.innerHTML = `<div class="text-red-400">Error: ${error.message}</div>`;
			}
		} finally {
			stopButton.classList.add("hidden");
			smoothScrollToBottom();
		}
	}

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
		smoothScrollToBottom();
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
		createTypingIndicator();
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
			formData.append("rag_mode_active", isRAGActive); // Add RAG mode state

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
				window.history.pushState({}, "", data.redirect_url);
				currentChatId = data.chat_id;
				isNewChat = false;
				const mobileHeader = document.querySelector(".md\\:hidden h1");
				if (mobileHeader && data.title) {
					mobileHeader.textContent = data.title;
				}
				const chatsList = document.getElementById("chats-list");
				const newChatElement = document.createElement("div");
				newChatElement.className =
					"flex items-center justify-between p-2 rounded bg-gray-700/40 transition-colors group text-sm";
				newChatElement.dataset.chatId = data.chat_id;
				newChatElement.innerHTML = `
					<div class="flex-1 truncate chat-title-container cursor-pointer" ondblclick="startEditing(this)">
						<div class="text-sm text-gray-200 truncate">${data.title}</div>
					</div>
					<div class="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
						<a href="/chat/${data.chat_id}/" class="p-1 text-gray-400 hover:text-gray-200 transition-all rounded">
							<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 7l5 5m0 0l-5 5m5-5H6"/>
							</svg>
						</a>
						<button class="delete-chat-btn p-1 text-gray-400 hover:text-gray-200 transition-all rounded" data-chat-id="${data.chat_id}" title="Delete chat">
							<svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor">
								<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"/>
							</svg>
						</button>
					</div>
				`;
				if (chatsList.firstChild) {
					chatsList.insertBefore(newChatElement, chatsList.firstChild);
				} else {
					chatsList.appendChild(newChatElement);
				}
				const deleteButton = newChatElement.querySelector(".delete-chat-btn");
				deleteButton.addEventListener("click", async (e) => {
					e.preventDefault();
					e.stopPropagation();
					// ... existing delete chat logic ...
				});
			}
			const streamResponse = await fetch(`/chat/${currentChatId}/stream/`, {
				method: "POST",
				body: formData,
				headers: {
					"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
						.value
				},
				signal: abortController.signal
			});
			await handleStreamResponse(streamResponse);
		} catch (error) {
			console.error("Error:", error);
			removeTypingIndicator();
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

	stopButton.addEventListener("click", () => {
		if (abortController) {
			abortController.abort();
			stopButton.classList.add("hidden");
			removeTypingIndicator();
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

	document.querySelectorAll(".delete-chat-btn").forEach((button) => {
		button.addEventListener("click", async (e) => {
			e.preventDefault();
			e.stopPropagation();
			const chatId = button.dataset.chatId;
			if (!confirm("Are you sure you want to delete this chat?")) return;
			try {
				const response = await fetch(`/chat/${chatId}/delete/`, {
					method: "POST",
					headers: {
						"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
							.value
					}
				});
				if (!response.ok) throw new Error("Failed to delete chat");
				const chatElement = button.closest("[data-chat-id]");
				if (chatElement) chatElement.remove();
				if (chatId === currentChatId) {
					window.location.href = "/chat/new/";
				}
			} catch (error) {
				console.error("Error deleting chat:", error);
				alert(
					"An error occurred when trying to delete the chat. Please refresh the page."
				);
			}
		});
	});

	window.startEditing = function (container) {
		const titleDiv = container.querySelector("div");
		const currentTitle = titleDiv.textContent.trim();
		const chatId = container.closest("[data-chat-id]").dataset.chatId;
		const input = document.createElement("input");
		input.type = "text";
		input.value = currentTitle;
		input.className =
			"w-full bg-gray-700/70 text-sm rounded px-2 py-1 text-gray-100 focus:outline-none focus:ring-1 focus:ring-gray-400";
		container.innerHTML = "";
		container.appendChild(input);
		input.focus();
		input.select();
		input.addEventListener("blur", () =>
			finishEditing(container, input, currentTitle, chatId)
		);
		input.addEventListener("keydown", (e) => {
			if (e.key === "Enter") {
				e.preventDefault();
				input.blur();
			} else if (e.key === "Escape") {
				restoreTitle(container, currentTitle);
			}
		});
	};

	async function finishEditing(container, input, originalTitle, chatId) {
		const newTitle = input.value.trim();
		if (!newTitle || newTitle === originalTitle) {
			restoreTitle(container, originalTitle);
			return;
		}
		try {
			const response = await fetch(`/chat/${chatId}/update-title/`, {
				method: "POST",
				headers: {
					"Content-Type": "application/json",
					"X-CSRFToken": document.querySelector("[name=csrfmiddlewaretoken]")
						.value
				},
				body: JSON.stringify({ title: newTitle })
			});
			if (!response.ok) throw new Error("Failed to update title");
			restoreTitle(container, newTitle);
			if (chatId === currentChatId) {
				const mobileHeader = document.querySelector(".md\\:hidden h1");
				if (mobileHeader) mobileHeader.textContent = newTitle;
				document.title = `${newTitle} - AI Chat Interface`;
			}
		} catch (error) {
			console.error("Error updating chat title:", error);
			restoreTitle(container, originalTitle);
			alert("Failed to update chat title. Please try again.");
		}
	}

	function restoreTitle(container, title) {
		container.textContent = title;
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
	const manageRagContextBtn = document.getElementById("manage-rag-context-btn");
	const ragModalOverlay = document.getElementById("rag-modal-overlay");
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
				"Please select a file to upload to RAG.",
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
					`Successfully added '${data.file.name}' to RAG context.`,
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
				`Successfully removed file from RAG context.`,
				"info"
			);
			fetchRAGFiles(); // Refresh the list
			// } else {
			//     throw new Error(data.error || 'Deletion reported unsuccessful by server.');
			// }
		} catch (error) {
			console.error("Error deleting RAG file:", error);
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
		const setActiveStyles = () => {
			ragToggleButton.textContent = "RAG Mode: Active";
			ragToggleButton.classList.remove("border-gray-600", "text-gray-400");
			ragToggleButton.classList.add("border-green-500", "text-green-400");
		};

		const setInactiveStyles = () => {
			ragToggleButton.textContent = "RAG Mode: Inactive";
			ragToggleButton.classList.remove("border-green-500", "text-green-400");
			ragToggleButton.classList.add("border-gray-600", "text-gray-400");
		};

		// Load RAG state from localStorage
		const savedRAGState = localStorage.getItem("ragModeActive");
		if (savedRAGState !== null) {
			isRAGActive = JSON.parse(savedRAGState);
		}

		// Initial styling based on loaded/default state
		if (isRAGActive) {
			setActiveStyles();
		} else {
			setInactiveStyles();
		}
		// Save the initial/loaded state back to localStorage in case it was newly defaulted
		localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));

		ragToggleButton.addEventListener("click", () => {
			isRAGActive = !isRAGActive;
			if (isRAGActive) {
				setActiveStyles();
			} else {
				setInactiveStyles();
			}
			// Save updated state to localStorage
			localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
			appendSystemNotification(
				`RAG mode is now ${isRAGActive ? "ACTIVE" : "INACTIVE"}.`,
				"info"
			);
		});
	}

	// Initialize code block features for messages already on the page
	document
		.querySelectorAll("#chat-messages .message-enter")
		.forEach((messageElement) => {
			if (typeof initializeCodeBlockFeatures === "function") {
				// We need to target the actual content div within the message element
				const contentDiv = messageElement.querySelector(
					".markdown-content, .quiz-message"
				);
				if (contentDiv) {
					initializeCodeBlockFeatures(contentDiv);
				}
			}
		});

	// Make necessary functions global for message_edit.js
	window.createTypingIndicator = createTypingIndicator;
	window.removeTypingIndicator = removeTypingIndicator;
	window.smoothScrollToBottom = smoothScrollToBottom;
	window.appendMessage = appendMessage; // Note: This is the patched version if _appendMessagePatched is true
	window.handleStreamResponse = handleStreamResponse;
	// getCookie and adjustMainTextareaHeight are already global
});

// Utility: Fix quiz-message blocks that are wrapped in <pre><code>
function unwrapQuizMessageCodeBlocks() {
	document.querySelectorAll(".quiz-message").forEach((quizMsg) => {
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

function fixEscapedQuizMessages() {
	document.querySelectorAll(".quiz-message pre code").forEach((code) => {
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

function fixFirstLineQuizPreCode() {
	document.querySelectorAll(".quiz-message").forEach((quizMsg) => {
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

// Global utility functions related to message display and interaction

// Standard getCookie function
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

// Image modal functions
function openImageModal(imgSrc) {
	// Create modal overlay if it doesn\'t exist
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
window.openImageModal = openImageModal; // Make it globally accessible

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
window.closeImageModal = closeImageModal; // Make it globally accessible

// Typing indicator functions will go here later
// Message appending functions will go here later
// Stream handling functions will go here later

document.addEventListener("DOMContentLoaded", function () {
    // DOM element selections for message handling
    const form = document.getElementById("chat-form");
    const textarea = document.getElementById("prompt");

    if (form && textarea) {
        // Submit form on Enter (without Shift)
        textarea.addEventListener("keydown", function (e) {
            if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                form.dispatchEvent(new Event("submit"));
            }
        });
    } else {
        console.warn("Chat form or prompt textarea not found for Enter key submission listener.");
    }
    
    // Other message handling initializations
});

// Typing indicator
function createTypingIndicator() {
    removeTypingIndicator(); // Ensure only one indicator exists

    const typingDiv = document.createElement("div");
    typingDiv.className = "message-enter px-4 md:px-6 py-6"; // Standard message styling
    typingDiv.id = "typing-indicator";

    // Using the same structure as assistant messages for consistency
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

    const messagesContainer = document.getElementById("chat-messages");
    if (messagesContainer) {
        messagesContainer.appendChild(typingDiv);
        smoothScrollToBottom();
    } else {
        console.warn("Chat messages container not found for typing indicator.");
    }
}
window.createTypingIndicator = createTypingIndicator; // Expose globally if needed by other modules

function removeTypingIndicator() {
    const typingIndicator = document.getElementById("typing-indicator");
    if (typingIndicator) {
        typingIndicator.remove();
    }
}
window.removeTypingIndicator = removeTypingIndicator; // Expose globally

// Smooth scroll to bottom of the chat
function smoothScrollToBottom() {
    const messagesContainer = document.getElementById("chat-messages") || document.body;
    // Check if a more specific container like 'chat-messages' exists and has content
    const targetScrollElement = document.documentElement.scrollHeight > document.body.scrollHeight ? document.documentElement : document.body;
    
    // Fallback to window scroll if chat-messages isn't the main scrollable area or not found
    const scrollTarget = messagesContainer.scrollHeight > messagesContainer.clientHeight ? messagesContainer : window;

    if (scrollTarget === window) {
        window.scrollTo({
            top: document.body.scrollHeight, // Scroll the whole page
            behavior: "smooth"
        });
    } else {
        scrollTarget.scrollTo({
            top: scrollTarget.scrollHeight, // Scroll within the container
            behavior: "smooth"
        });
    }
}
window.smoothScrollToBottom = smoothScrollToBottom; // Expose globally 


// --- Core Message Handling Functions (Moved from chat.js) ---

// Function to append a system notification to the chat.
// Exposed globally as it\'s used by other modules (e.g., RAG modal, mode toggles)
window.appendSystemNotification = function(message, level = "info") {
    const messagesDiv = document.getElementById("chat-messages");
    if (!messagesDiv) {
        console.warn("Chat messages container not found for system notification.");
        // Optionally, alert the message as a fallback
        // alert(`System Notification (${level}): ${message}`);
        return;
    }
    const notificationDiv = document.createElement("div");
    notificationDiv.className = "message-enter px-4 md:px-6 py-3"; 

    let bgColor = "bg-gray-700/70"; 
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
    if (typeof window.smoothScrollToBottom === 'function') window.smoothScrollToBottom();
};


// Main function to append a message to the chat UI.
// Returns the content element that might need further updates (e.g., for streaming).
// Relies on window.initializeQuizForms, window.unwrapQuizMessageCodeBlocks, etc. from quiz.js
// Relies on window.initializeCodeBlockFeatures from code_block_feature.js
// Relies on window.openImageModal from this file.
window.appendMessage = function(role, content, messageId = null, type = "text", quizHtml = null, isEdited = false, editedAt = null) {
    const messagesContainer = document.getElementById("chat-messages");
    if (!messagesContainer) {
        console.error("Chat messages container not found!");
        return null;
    }
    
    // Remove placeholder if it exists
    const placeholder = messagesContainer.querySelector(".flex.flex-col.items-center.justify-center.h-\[calc\(100vh-200px\)\]");
    if (placeholder) placeholder.remove();

    const messageDiv = document.createElement("div");
    messageDiv.className = "message-enter px-4 md:px-6 py-6";
    if (messageId) messageDiv.setAttribute("data-message-id", messageId);
    
    let contentElementToReturn = null; 

    if (role === "user") {
        messageDiv.innerHTML = `
            <div class="chat-container flex flex-row-reverse gap-4 md:gap-6 justify-start">
                <div class="flex-shrink-0 w-7 h-7">
                    <div class="w-7 h-7 rounded-sm bg-[#5436DA] flex items-center justify-center text-white text-xs font-semibold">U</div>
                </div>
                <div class="overflow-x-auto max-w-[75%]">
                    <div class="user-message text-gray-100 bg-[#444654] p-3 rounded-lg message-text-container group" data-message-id="${messageId || ''}" data-created-at="${new Date().toISOString()}">
                        <p class="whitespace-pre-wrap message-content-text">${content}</p>
                        <div class="edit-controls hidden mt-2">
                            <textarea class="edit-message-textarea w-full p-2 rounded bg-gray-700 border border-gray-600 text-gray-100 resize-none" rows="3"></textarea>
                            <div class="flex justify-end gap-2 mt-2">
                                <button class="cancel-edit-btn px-3 py-1 text-xs bg-gray-600 hover:bg-gray-500 rounded text-white">Cancel</button>
                                <button class="save-edit-btn px-3 py-1 text-xs bg-blue-600 hover:bg-blue-500 rounded text-white">Save</button>
                            </div>
                        </div>
                        ${isEdited ? '<span class="text-xs text-gray-400 italic ml-1 edited-indicator">(edited)</span>' : ''}
                    </div>
                    <div class="flex justify-end mt-1 pr-1">
                        <button class="edit-message-btn opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-gray-200 transition-opacity" data-message-id="${messageId || ''}" title="Edit message">
                            <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                                <path stroke-linecap="round" stroke-linejoin="round" d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
                            </svg>
                        </button>
                    </div>
                </div>
            </div>
        `;
        contentElementToReturn = messageDiv.querySelector('.message-content-text');
    } else { // Assistant messages
        messageDiv.innerHTML = `
            <div class="chat-container flex gap-4 md:gap-6">
                <div class="flex-shrink-0 w-7 h-7">
                    <div class="cls w-10 h-7 p-1 rounded-sm bg-slate-100 flex items-center justify-center text-white">
                        <img src="/static/images/logo.png" alt="Assistant icon" class="h-5 w-7">
                    </div>
                </div>
                <div class="flex-1 overflow-x-auto min-w-0 max-w-[85%]" data-role="assistant-content-wrapper">
                    <!-- Content will be injected here based on type -->
                </div>
            </div>
        `;
        const assistantContentWrapper = messageDiv.querySelector('[data-role="assistant-content-wrapper"]');

        if (type === "quiz" && quizHtml) {
            const quizDiv = document.createElement('div');
            quizDiv.className = "quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl";
            quizDiv.innerHTML = quizHtml;
            assistantContentWrapper.appendChild(quizDiv);
            contentElementToReturn = quizDiv;
            // Apply quiz fixes and initialize forms
            setTimeout(() => { // Timeout to ensure DOM is ready
                if (typeof window.unwrapQuizMessageCodeBlocks === 'function') window.unwrapQuizMessageCodeBlocks(quizDiv);
                if (typeof window.fixEscapedQuizMessages === 'function') window.fixEscapedQuizMessages(quizDiv);
                if (typeof window.fixFirstLineQuizPreCode === 'function') window.fixFirstLineQuizPreCode(quizDiv);
                if (typeof window.initializeQuizForms === 'function') window.initializeQuizForms(quizDiv);
            }, 0);
        } else if (type === "diagram" && content) { // content is the image URL for diagrams
            const diagramDiv = document.createElement('div');
            diagramDiv.className = "diagram-message-container bg-gray-800/50 p-2 my-2 rounded-lg shadow-md flex flex-col justify-center items-center";
            diagramDiv.innerHTML = `
                <img src="${content}" alt="${messageId || 'Generated Diagram'}" 
                     class="max-w-full h-auto rounded-md mb-1 cursor-pointer hover:opacity-90 transition-opacity" 
                     onclick="window.openImageModal('${content}')">
                ${messageId ? `<p class="text-xs text-gray-400 italic mt-1 text-center">${messageId}</p>` : ""}
            `; // Using messageId as alt text if diagram description not available separately
            assistantContentWrapper.appendChild(diagramDiv);
            contentElementToReturn = diagramDiv;
        } else { // Default to text type
            const markdownDiv = document.createElement('div');
            markdownDiv.className = "max-w-none markdown-content text-gray-100";
            markdownDiv.dataset.rawTextBuffer = content || ""; // Initialize buffer
            
            if (typeof marked !== 'undefined') {
                marked.setOptions({ breaks: false, gfm: true });
                markdownDiv.innerHTML = marked.parse(content || "");
                if (typeof hljs !== 'undefined') {
                    markdownDiv.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
                }
                if (typeof window.initializeCodeBlockFeatures === 'function') {
                     setTimeout(() => window.initializeCodeBlockFeatures(markdownDiv), 0); // Ensure DOM ready
                }
            } else {
                markdownDiv.textContent = content || ""; // Fallback
            }
            assistantContentWrapper.appendChild(markdownDiv);
            contentElementToReturn = markdownDiv;
        }
    }

    messagesContainer.appendChild(messageDiv);
    if (typeof window.smoothScrollToBottom === 'function') window.smoothScrollToBottom();
    
    // Initialize message editing for user messages
    if (role === 'user' && typeof window.initializeMessageEditing === 'function') {
        const userMessageContainer = messageDiv.querySelector('.user-message');
        if (userMessageContainer) window.initializeMessageEditing(userMessageContainer);
    }

    return contentElementToReturn; 
};

// Specific function to append a user message, simplifies calls from form submit.
// Relies on window.appendMessage.
window.appendUserMessage = function(content, messageId = null, isEdited = false, editedAt = null) {
    // No need to remove placeholder here, appendMessage handles it.
    return window.appendMessage("user", content, messageId, "text", null, isEdited, editedAt);
};

// Specific function to append a diagram message.
// Relies on window.appendMessage.
window.appendDiagramMessage = function(imageUrl, textContent, messageId = null) {
    // textContent is used as the description under the image, messageId is for the alt if textContent is missing
    // The actual image src is imageUrl.
    // appendMessage for assistant with type "diagram" expects the image URL in the 'content' field,
    // and the descriptive text (if any) in the 'messageId' field for this specific appendMessage call.
    return window.appendMessage("assistant", imageUrl, textContent || "Generated Diagram", "diagram", null);
};

// Function to update an assistant\'s message content, typically during streaming.
// Relies on window.initializeCodeBlockFeatures and quiz helper functions.
window.updateAssistantMessage = function(container, contentChunk) {
    if (!container) {
        console.warn("Attempted to update a null message container.");
        return;
    }

    const isQuizContent = container.classList.contains("quiz-message");

    if (isQuizContent) {
        // For quiz, contentChunk is expected to be the full HTML. Replace.
        container.innerHTML = contentChunk;
        setTimeout(() => { // Ensure DOM is updated
            if (typeof window.unwrapQuizMessageCodeBlocks === 'function') window.unwrapQuizMessageCodeBlocks(container);
            if (typeof window.fixEscapedQuizMessages === 'function') window.fixEscapedQuizMessages(container);
            if (typeof window.fixFirstLineQuizPreCode === 'function') window.fixFirstLineQuizPreCode(container);
            if (typeof window.initializeQuizForms === 'function') window.initializeQuizForms(container);
        }, 0);
    } else if (container.classList.contains("markdown-content")) {
        // For markdown text, append and re-parse
        if (typeof container.dataset.rawTextBuffer === 'undefined') {
            container.dataset.rawTextBuffer = ""; 
        }
        container.dataset.rawTextBuffer += contentChunk;

        if (typeof marked !== 'undefined' && typeof hljs !== 'undefined') {
            marked.setOptions({ breaks: false, gfm: true });
            container.innerHTML = marked.parse(container.dataset.rawTextBuffer);
            container.querySelectorAll("pre code").forEach((block) => hljs.highlightElement(block));
            if (typeof window.initializeCodeBlockFeatures === 'function') {
                // Re-initialize for potentially new/modified code blocks
                 setTimeout(() => window.initializeCodeBlockFeatures(container), 0);
            }
        } else {
            container.textContent = container.dataset.rawTextBuffer; // Fallback
        }
    } else {
        // Fallback for other types or if container is not the expected markdown/quiz div
        container.textContent += contentChunk;
    }
    if (typeof window.smoothScrollToBottom === 'function') window.smoothScrollToBottom();
};


// Function to handle the Server-Sent Event stream for chat responses.
// Relies on window.appendMessage, window.updateAssistantMessage, 
// window.appendSystemNotification, window.removeTypingIndicator.
window.handleStreamResponse = async function(response, currentChatId) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let currentMessageContainer = null; 
    let isFirstTextChunk = true;
    let assistantMessageId = null; // To store message_id if provided by stream for assistant message

    try {
        while (true) {
            const { value, done } = await reader.read();
            if (done) break;

            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split("\n"); // SSE lines are separated by \n
            buffer = lines.pop() || ""; // Keep the last incomplete line in buffer

            for (const line of lines) {
                if (line.startsWith("data: ")) {
                    const dataString = line.slice(6);
                    if (!dataString.trim()) continue; // Skip empty data lines

                    try {
                        const data = JSON.parse(dataString);
                        assistantMessageId = data.message_id || assistantMessageId; // Persist assistant message_id

                        if (data.type === "quiz") {
                            if (isFirstTextChunk) { 
                                currentMessageContainer = window.appendMessage(
                                    "assistant", 
                                    "", // Content is in quizHtml
                                    data.message_id, // Use ID from server
                                    "quiz", 
                                    data.quiz_html
                                );
                                isFirstTextChunk = false;
                            }
                        } else if (data.type === "content") {
                            if (isFirstTextChunk) {
                                currentMessageContainer = window.appendMessage(
                                    "assistant",
                                    data.content, 
                                    assistantMessageId, // Pass ID if available
                                    "text"
                                );
                                isFirstTextChunk = false;
                            } else if (currentMessageContainer) {
                                window.updateAssistantMessage(currentMessageContainer, data.content);
                            }
                        } else if (data.type === "diagram_image") {
                            if (data.image_url) {
                                currentMessageContainer = window.appendDiagramMessage(
                                    data.image_url, 
                                    data.text_content || "Generated Diagram",
                                    data.message_id // Use ID from server for the diagram message
                                );
                                isFirstTextChunk = false; 
                            } else {
                                window.appendSystemNotification("Error: Received diagram response without image URL", "error");
                            }
                        } else if (data.type === "error") {
                            window.appendSystemNotification(data.content, "error");
                             if (typeof window.removeTypingIndicator === 'function') window.removeTypingIndicator(); // Stop typing on error
                        } else if (data.type === "file_info") { // Handle file truncation warnings
                            if (data.status === 'truncated' && data.message) {
                                window.appendSystemNotification(data.message, "warning");
                            }
                        } else if (data.type === "done") {
                             if (typeof window.removeTypingIndicator === 'function') window.removeTypingIndicator();
                            // Potentially do final processing on currentMessageContainer if needed
                        } else if (data.type === "metadata") {
                            // Handle RAG metadata if needed (e.g., display source chunks)
                            // console.log("Received metadata:", data.content);
                        }
                    } catch (e) {
                        console.error("Error parsing JSON from stream data:", dataString, e);
                        // Optionally, display a generic error to the user for this chunk
                    }
                }
            }
        }
    } catch (error) {
        console.error("Error processing stream:", error);
        window.appendSystemNotification("An error occurred while processing the response.", "error");
    } finally {
        if (typeof window.removeTypingIndicator === 'function') window.removeTypingIndicator();
    }
}; 
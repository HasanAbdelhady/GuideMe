window.StreamHandler = {
	// This function is a helper for handleStreamResponse
	updateAssistantMessage: function (container, contentChunk) {
		// container is now expected to be the <code class="streaming-text"> element
		if (container && container.classList.contains("streaming-text")) {
			// Simply append new text for a live "typing" effect
			container.textContent += contentChunk;
			window.smoothScrollToBottom();
		} else {
			// Fallback for non-streaming updates or other content types.
			console.warn(
				"updateAssistantMessage called on a non-streaming container or container is null.",
				container
			);
			if (container && container.dataset) {
				container.dataset.rawTextBuffer =
					(container.dataset.rawTextBuffer || "") + contentChunk;
				container.innerHTML = marked.parse(container.dataset.rawTextBuffer);
				container
					.querySelectorAll("pre code")
					.forEach((block) => hljs.highlightElement(block));
				initializeCodeBlockFeatures(container);
				window.smoothScrollToBottom();
			}
		}
	},

	// Main function to process the server's event stream
	handleStreamResponse: async function (response) {
		const reader = response.body.getReader();
		const decoder = new TextDecoder();
		let buffer = "";
		let currentMessageContainer = null; // This will hold the .streaming-text code element
		let isFirstTextChunk = true;
		let isMixedContentMessage = false;
		let mixedContentElements = [];
		let toolResultCount = 0;
		let streamFinished = false;
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
				resetTimeout();
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
											window.ChatUI.renderAndAppendQuiz(quizData);
										}
									})
									.catch((error) => {
										console.error(
											"Error fetching agent-generated quiz:",
											error
										);
										window.ChatUI.appendSystemNotification(
											`Error rendering quiz: ${error.message}`,
											"error"
										);
									});
							}
							isFirstTextChunk = true;
							currentMessageContainer = null;
							toolResultCount = 0;
						} else if (data.type === "quiz") {
							window.removeTypingIndicator();
							window.appendMessage(
								"assistant",
								data.content || "Here is your quiz:",
								data.message_id,
								"quiz",
								data.quiz_html
							);
							currentMessageContainer = null;
							isFirstTextChunk = true;
							toolResultCount = 0;
						} else if (data.type === "quiz_html") {
							toolResultCount++;
							if (
								!isMixedContentMessage &&
								(mixedContentElements.length > 0 || currentMessageContainer)
							) {
								isMixedContentMessage = true;
							}
							if (isMixedContentMessage) {
								const quizElement =
									this.createQuizElement(data.quiz_html);
								quizElement.dataset.order = data.order || toolResultCount;
								mixedContentElements.push({
									element: quizElement,
									order: parseInt(data.order) || toolResultCount,
									type: "quiz"
								});
							} else {
								window.removeTypingIndicator();
								window.ChatUI.renderAndAppendQuiz({ quiz_html: data.quiz_html });
							}
						} else if (data.type === "mixed_content_start") {
							isMixedContentMessage = true;
							mixedContentElements = [];
							toolResultCount = 0;
						} else if (data.type === "content") {
							if (!isMixedContentMessage && mixedContentElements.length > 0) {
								isMixedContentMessage = true;
							}
							if (isFirstTextChunk) {
								currentMessageContainer =
									window.transformTypingIndicatorToMessage(
										data.content,
										"text"
									);
								isFirstTextChunk = false;
							} else {
								this.updateAssistantMessage(
									currentMessageContainer,
									data.content
								);
							}
						} else if (data.type === "error") {
							window.ChatUI.appendSystemNotification(data.content, "error");
						} else if (data.type === "diagram_image") {
							toolResultCount++;
							if (data.diagram_image_id) {
								const imageUrl = `/chat/diagram_image/${data.diagram_image_id}/`;
								if (
									!isMixedContentMessage &&
									(mixedContentElements.length > 0 || currentMessageContainer)
								) {
									isMixedContentMessage = true;
								}
								if (isMixedContentMessage) {
									const diagramElement = this.createDiagramElement(
										imageUrl,
										data.text_content || "Generated Diagram"
									);
									diagramElement.dataset.order =
										data.order || toolResultCount;
									mixedContentElements.push({
										element: diagramElement,
										order: parseInt(data.order) || toolResultCount,
										type: "diagram"
									});
								} else {
									window.removeTypingIndicator();
									this.appendDiagramMessage(
										imageUrl,
										data.text_content || "Generated Diagram",
										data.message_id
									);
									currentMessageContainer = null;
									isFirstTextChunk = true;
								}
							} else {
								window.ChatUI.appendSystemNotification(
									"Error: Received diagram response without diagram_image_id",
									"error"
								);
							}
						} else if (data.type === "done") {
							if (
								currentMessageContainer &&
								currentMessageContainer.classList.contains("streaming-text")
							) {
								const markdownWrapper = currentMessageContainer.closest(
									".markdown-content.streaming"
								);
								if (markdownWrapper) {
									const rawText = currentMessageContainer.textContent;
									const parsedHtml = marked.parse(rawText);
									markdownWrapper.innerHTML = parsedHtml;
									markdownWrapper.classList.remove("streaming");
									markdownWrapper
										.querySelectorAll("pre code")
										.forEach((block) => {
											hljs.highlightElement(block);
										});
									initializeCodeBlockFeatures(markdownWrapper);
								}
							}
							if (
								(isMixedContentMessage && mixedContentElements.length > 0) ||
								toolResultCount > 1
							) {
								this.createMixedContentMessage(
									mixedContentElements,
									currentMessageContainer
								);
								isMixedContentMessage = false;
								mixedContentElements = [];
								currentMessageContainer = null;
								isFirstTextChunk = true;
								toolResultCount = 0;
							}
							window.removeTypingIndicator();
							streamFinished = true;
						} else if (data.type === "youtube_recommendations") {
							toolResultCount++;
							if (
								!isMixedContentMessage &&
								(mixedContentElements.length > 0 || currentMessageContainer)
							) {
								isMixedContentMessage = true;
							}
							if (isMixedContentMessage) {
								const youtubeElement = this.createYoutubeElement(data.data);
								youtubeElement.dataset.order = data.order || toolResultCount;
								mixedContentElements.push({
									element: youtubeElement,
									order: parseInt(data.order) || toolResultCount,
									type: "youtube"
								});
							} else {
								window.removeTypingIndicator();
								const messagesContainer =
									document.getElementById("chat-messages");
								const placeholder = document.getElementById(
									"initial-chat-placeholder"
								);
								if (placeholder) placeholder.remove();
								const messageDiv = document.createElement("div");
								messageDiv.className = "message-enter px-4 md:px-6 py-6";
								messageDiv.innerHTML =
									window.ChatUI.createAssistantMessageStructure(`
									<div data-role="youtube-content-wrapper"></div>
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
								currentMessageContainer = null;
								isFirstTextChunk = true;
							}
						}
					}
				}

				await new Promise((resolve) => setTimeout(resolve, 1));

				if (streamFinished) {
					break;
				}
			}
		} catch (error) {
			console.error("Error in handleStreamResponse:", error);
			window.removeTypingIndicator();
		} finally {
			clearTimeout(streamTimeout);
		}
	},

	appendDiagramMessage: function (imageUrl, textContent, messageId) {
		const messagesDiv = document.getElementById("chat-messages");
		const placeholder = document.getElementById("initial-chat-placeholder");
		if (placeholder) placeholder.remove();

		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		messageDiv.setAttribute("data-message-id", messageId);

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

		messageDiv.innerHTML =
			window.ChatUI.createAssistantMessageStructure(diagramContentHtml);

		messagesDiv.appendChild(messageDiv);
		window.smoothScrollToBottom();
	},

	// Helper functions for mixed content messages
	createDiagramElement: function (imageUrl, textContent) {
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
	},

	createYoutubeElement: function (videos) {
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
	},

	createQuizElement: function (quizHtml) {
		const quizDiv = document.createElement("div");
		quizDiv.className =
			"quiz-message max-w-none text-gray-100 bg-gray-700/70 p-2 rounded-xl";
		quizDiv.innerHTML = `
			<div class="quiz-content">
				<div class="quiz-message">${quizHtml}</div>
			</div>
		`;
		const quizMessage = quizDiv.querySelector(".quiz-message");
		if (quizMessage) {
			window.ChatUI.unwrapQuizMessageCodeBlocks(quizMessage);
			window.ChatUI.fixEscapedQuizMessages(quizMessage);
			window.ChatUI.fixFirstLineQuizPreCode(quizMessage);
			window.ChatUI.initializeQuizForms(quizMessage);
		}
		return quizDiv;
	},

	createMixedContentMessage: function (mixedElements, textContainer) {
		const messagesContainer = document.getElementById("chat-messages");
		const placeholder = document.getElementById("initial-chat-placeholder");
		if (placeholder) placeholder.remove();

		const messageDiv = document.createElement("div");
		messageDiv.className = "message-enter px-4 md:px-6 py-6";
		messageDiv.innerHTML = window.ChatUI.createAssistantMessageStructure(`
			<div data-role="mixed-content-wrapper"></div>
		`);
		const contentWrapper = messageDiv.querySelector(
			'[data-role="mixed-content-wrapper"]'
		);

		if (textContainer && textContainer.classList.contains("streaming-text")) {
			const textDiv = document.createElement("div");
			textDiv.className = "text-component markdown-content mb-4";
			const rawText = textContainer.textContent;
			if (typeof marked !== "undefined" && typeof hljs !== "undefined") {
				marked.setOptions({
					breaks: false,
					gfm: true
				});
				const parsedHtml = marked.parse(rawText);
				textDiv.innerHTML = parsedHtml;
				textDiv.querySelectorAll("pre code").forEach((block) => {
					hljs.highlightElement(block);
				});
				initializeCodeBlockFeatures(textDiv);
			} else {
				textDiv.textContent = rawText;
			}
			contentWrapper.appendChild(textDiv);
		}

		if (Array.isArray(mixedElements) && mixedElements.length > 0) {
			if (
				mixedElements[0] &&
				typeof mixedElements[0] === "object" &&
				mixedElements[0].element
			) {
				const sortedElements = mixedElements
					.sort((a, b) => (a.order || 0) - (b.order || 0))
					.map((item) => {
						return item.element;
					});
				sortedElements.forEach((element) => {
					contentWrapper.appendChild(element);
				});
			} else {
				mixedElements.forEach((element) => {
					contentWrapper.appendChild(element);
				});
			}
		}

		messagesContainer.appendChild(messageDiv);
		window.ChatUI.applyConsistentChatElementStyling(messageDiv);
		window.smoothScrollToBottom();

		if (textContainer && textContainer.closest(".message-enter")) {
			textContainer.closest(".message-enter").remove();
		}
	}
}; 
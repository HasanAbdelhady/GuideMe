// RAG Context Management Modal Functionality

// Depends on global: window.currentChatId, window.isNewChat, window.getCookie, window.appendSystemNotification

document.addEventListener("DOMContentLoaded", function () {
	const manageRagContextBtn = document.getElementById("manage-rag-context-btn");
	const ragModalOverlay = document.getElementById("rag-modal-overlay");
	const ragModalContent = document.getElementById("rag-modal-content");
	const closeRagModalBtn = document.getElementById("close-rag-modal-btn");
	const ragFilesListDiv = document.getElementById("rag-files-list");
	const noRagFilesMessage = document.getElementById("no-rag-files-message");
	const ragFileInput = document.getElementById("rag-file-input"); // Modal's file input
	const uploadRagFileBtn = document.getElementById("upload-rag-file-btn");
	const ragFileCountSpan = document.getElementById("rag-file-count");
	const ragUploadSection = document.getElementById("rag-upload-section");
	const ragLimitReachedMessage = document.getElementById(
		"rag-limit-reached-message"
	);

	if (
		!manageRagContextBtn ||
		!ragModalOverlay ||
		!ragModalContent ||
		!closeRagModalBtn ||
		!ragFilesListDiv ||
		!noRagFilesMessage ||
		!ragFileInput ||
		!uploadRagFileBtn ||
		!ragFileCountSpan ||
		!ragUploadSection ||
		!ragLimitReachedMessage
	) {
		console.warn(
			"One or more RAG modal elements not found. RAG context management might not work."
		);
		// return; // Allow partial functionality if some elements are missing for some reason
	}

	let currentRAGFiles = []; // Stores {id: '...', name: '...'} objects
	const MAX_RAG_FILES = 10;

	function openRAGModal() {
		if (!ragModalOverlay || !ragModalContent) return;
		ragModalOverlay.classList.remove("opacity-0", "pointer-events-none");
		ragModalContent.classList.remove("scale-95");
		ragModalContent.classList.add("scale-100");
		fetchRAGFiles(); // Fetch files when modal opens
	}
	window.openRAGModal = openRAGModal; // Expose globally if needed

	function closeRAGModal() {
		if (!ragModalOverlay || !ragModalContent) return;
		ragModalOverlay.classList.add("opacity-0");
		ragModalContent.classList.add("scale-95");
		ragModalContent.classList.remove("scale-100");
		setTimeout(() => {
			ragModalOverlay.classList.add("pointer-events-none");
		}, 300); // Corresponds to transition duration
	}
	window.closeRAGModal = closeRAGModal; // Expose globally

	function renderRAGFilesList(files) {
		if (!ragFilesListDiv || !noRagFilesMessage) {
			console.warn(
				"RAG file list or no-files message element not found for rendering."
			);
			return;
		}
		currentRAGFiles = files;
		ragFilesListDiv.innerHTML = ""; // Clear previous list

		if (files.length === 0) {
			noRagFilesMessage.classList.remove("hidden");
		} else {
			noRagFilesMessage.classList.add("hidden");
			files.forEach((file) => {
				const fileEl = document.createElement("div");
				fileEl.className =
					"flex items-center justify-between bg-gray-700 p-2 rounded-md text-sm hover:bg-gray-600/80 transition-colors";
				fileEl.innerHTML = `
                    <span class="text-gray-200 truncate max-w-[80%]" title="${file.name}">${file.name}</span>
                    <button class="delete-rag-file-btn p-1 text-red-400 hover:text-red-300 rounded-full focus:outline-none focus:ring-2 focus:ring-red-500 focus:ring-opacity-50" data-file-id="${file.id}" title="Remove from RAG context">
                        <svg xmlns="http://www.w3.org/2000/svg" class="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2">
                            <path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12" />
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
		) {
			console.warn("One or more RAG limit view elements not found.");
			return;
		}
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
		if (
			window.isNewChat ||
			!window.currentChatId ||
			window.currentChatId === "new"
		) {
			renderRAGFilesList([]);
			return;
		}
		try {
			const response = await fetch(`/chat/${window.currentChatId}/rag-files/`);
			if (!response.ok) {
				const errorData = await response.json();
				throw new Error(errorData.error || "Failed to fetch RAG files");
			}
			const files = await response.json();
			renderRAGFilesList(files);
		} catch (error) {
			console.error("Error fetching RAG files:", error);
			if (window.appendSystemNotification)
				window.appendSystemNotification(
					"Could not load RAG files: " + error.message,
					"error"
				);
			renderRAGFilesList([]);
		}
	}

	async function handleRAGFileUpload() {
		if (
			window.isNewChat ||
			!window.currentChatId ||
			window.currentChatId === "new"
		)
			return;
		if (!ragFileInput) {
			console.error("RAG file input not found for upload.");
			return;
		}
		const file = ragFileInput.files[0];
		if (!file) {
			if (window.appendSystemNotification)
				window.appendSystemNotification(
					"Please select a file to upload to RAG.",
					"warning"
				);
			return;
		}

		const formData = new FormData();
		formData.append("file", file);
		// CSRF token should be available via window.getCookie, or ensure it's handled if not a top-level form submission
		const csrfToken = window.getCookie("csrftoken");
		if (csrfToken) {
			// Typically not needed for FormData directly unless backend specifically expects it in header for non-form posts
			// formData.append("csrfmiddlewaretoken", csrfToken);
		} else {
			console.warn("CSRF token not found for RAG file upload.");
		}

		try {
			uploadRagFileBtn.disabled = true;
			uploadRagFileBtn.textContent = "Uploading...";
			const response = await fetch(`/chat/${window.currentChatId}/rag-files/`, {
				method: "POST",
				body: formData,
				headers: {
					// Django often needs CSRF token for POST, even with FormData for AJAX
					"X-CSRFToken": csrfToken
				}
			});
			const data = await response.json();
			if (!response.ok)
				throw new Error(
					data.error || `Failed to upload file (status: ${response.status})`
				);
			if (data.success && data.file) {
				if (window.appendSystemNotification)
					window.appendSystemNotification(
						`Successfully added '${data.file.name}' to RAG context.`,
						"info"
					);
				fetchRAGFiles();
			} else {
				throw new Error(
					data.error || "Upload completed but response format was unexpected."
				);
			}
		} catch (error) {
			console.error("Error uploading RAG file:", error);
			if (window.appendSystemNotification)
				window.appendSystemNotification(
					`Upload failed: ${error.message}`,
					"error"
				);
		} finally {
			if (uploadRagFileBtn) {
				uploadRagFileBtn.disabled = false;
				uploadRagFileBtn.textContent = "Add to RAG";
			}
			if (ragFileInput) ragFileInput.value = ""; // Clear the input
		}
	}

	async function handleDeleteRAGFile(fileId) {
		if (
			window.isNewChat ||
			!window.currentChatId ||
			window.currentChatId === "new"
		)
			return;
		if (
			!confirm(
				"Are you sure you want to remove this file from the RAG context?"
			)
		)
			return;

		const csrfToken = window.getCookie("csrftoken");
		if (!csrfToken) {
			console.error("CSRF token not found for deleting RAG file.");
			if (window.appendSystemNotification)
				window.appendSystemNotification(
					"Action failed: Missing security token.",
					"error"
				);
			return;
		}

		try {
			const response = await fetch(
				`/chat/${window.currentChatId}/rag-files/${fileId}/delete/`,
				{
					method: "DELETE",
					headers: {
						"X-CSRFToken": csrfToken,
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
			// No JSON response expected for a successful DELETE often (204 No Content)
			if (window.appendSystemNotification)
				window.appendSystemNotification(
					"Successfully removed file from RAG context.",
					"info"
				);
			fetchRAGFiles();
		} catch (error) {
			console.error("Error deleting RAG file:", error);
			if (window.appendSystemNotification)
				window.appendSystemNotification(
					`Failed to remove file: ${error.message}`,
					"error"
				);
		}
	}

	// Event Listeners for modal interaction
	if (manageRagContextBtn)
		manageRagContextBtn.addEventListener("click", openRAGModal);
	if (closeRagModalBtn)
		closeRagModalBtn.addEventListener("click", closeRAGModal);
	if (ragModalOverlay) {
		ragModalOverlay.addEventListener("click", function (event) {
			if (event.target === ragModalOverlay) closeRAGModal();
		});
	}
	if (uploadRagFileBtn)
		uploadRagFileBtn.addEventListener("click", handleRAGFileUpload);

	// Initial visibility update for the manage RAG button
	function updateManageRagButtonVisibility() {
		if (manageRagContextBtn) {
			if (
				window.isNewChat ||
				!window.currentChatId ||
				window.currentChatId === "new"
			) {
				manageRagContextBtn.classList.add("hidden");
			} else {
				manageRagContextBtn.classList.remove("hidden");
			}
		}
	}
	updateManageRagButtonVisibility();
	// Listen to chat changes if other modules emit such events, or re-evaluate on new chat creation if needed.
	// For now, this is set on DOMContentLoaded based on initial window.isNewChat.

	// Listen for the custom event dispatched by chat.js
	document.addEventListener("chatStateChanged", function (event) {
		console.log(
			"[rag_modal_handler.js] Caught chatStateChanged event",
			event.detail
		);
		// window.isNewChat and window.currentChatId should be updated by chat.js before this event
		updateManageRagButtonVisibility();
	});
});

// static/chat/code_block_features.js

function initializeCodeBlockFeatures(messageElement) {
	const codeBlocks = messageElement.querySelectorAll("pre"); // Target 'pre' elements which usually wrap 'code'

	codeBlocks.forEach((preElement) => {
		if (preElement.querySelector("code")) {
			// Ensure there's a code element inside
			// Prevent adding buttons multiple times
			if (preElement.dataset.featuresInitialized) {
				return;
			}
			preElement.dataset.featuresInitialized = "true";

			if (!preElement.parentNode) {
				console.warn(
					"Code block PRE element has no parentNode, cannot add features.",
					preElement
				);
				return;
			}

			const wrapper = document.createElement("div");
			wrapper.style.position = "relative"; // Remains relative for normal state

			// Create a button container
			const buttonContainer = document.createElement("div");
			buttonContainer.className = "code-block-buttons"; // Add a class for styling
			// Style for button container (position top-right, etc.)
			buttonContainer.style.position = "absolute";
			buttonContainer.style.top = "0.5em";
			buttonContainer.style.right = "0.5em";
			buttonContainer.style.zIndex = "10"; // Ensure buttons are above pre in canvas too
			buttonContainer.style.display = "flex";
			buttonContainer.style.gap = "0.5em";

			// 1. Create Copy Button
			const copyButton = document.createElement("button");
			copyButton.textContent = "Copy";
			copyButton.className = "code-block-copy-btn"; // Add a class for styling
			// Basic styling for buttons (can be moved to CSS)
			styleButton(copyButton);

			copyButton.addEventListener("click", () => {
				const codeContent = preElement.querySelector("code").innerText;
				navigator.clipboard
					.writeText(codeContent)
					.then(() => {
						copyButton.textContent = "Copied!";
						setTimeout(() => {
							copyButton.textContent = "Copy";
						}, 2000);
					})
					.catch((err) => {
						console.error("Failed to copy text: ", err);
						// Optionally provide user feedback for error
					});
			});

			// 2. Create Expand/Collapse Button
			const expandButton = document.createElement("button");
			expandButton.textContent = "Expand"; // Initial text
			expandButton.className = "code-block-expand-btn"; // Add a class for styling
			styleButton(expandButton);

			// Add a class to the pre element for default styling (e.g., max-height)
			preElement.classList.add("code-block-collapsible");

			// Explicitly set initial collapsed state via inline styles
			const collapsedHeight = "300px"; // Must match CSS .code-block-collapsible max-height
			preElement.style.maxHeight = collapsedHeight;
			preElement.style.overflowY = "hidden";
			let isCurrentlyExpanded = false;
			let isInCanvasMode = false; // New state for canvas mode

			expandButton.addEventListener("click", () => {
				if (!isInCanvasMode) {
					// First click: Expand vertically or enter canvas mode
					// For this version, let's make it go to canvas mode directly
					wrapper.classList.add("code-block-wrapper-canvas-mode");
					document.body.classList.add("code-canvas-backdrop-active"); // Optional: if you want a backdrop
					preElement.style.maxHeight = "none"; // Allow full height within canvas
					preElement.style.height = "100%"; // Explicitly take full height
					preElement.style.width = "100%"; // Explicitly take full width
					preElement.style.overflow = "auto"; // General scroll
					expandButton.textContent = "Minimize";
					isInCanvasMode = true;
					isCurrentlyExpanded = true; // Implied by canvas mode
				} else {
					// Second click: Minimize from canvas mode
					wrapper.classList.remove("code-block-wrapper-canvas-mode");
					document.body.classList.remove("code-canvas-backdrop-active"); // Optional
					preElement.style.maxHeight = collapsedHeight;
					preElement.style.height = ""; // Reset height to allow max-height to work
					preElement.style.width = ""; // Reset width
					preElement.style.overflowY = "hidden";
					preElement.style.overflowX = "auto"; // Or your default for horizontal scroll in normal view
					expandButton.textContent = "Expand";
					isInCanvasMode = false;
					isCurrentlyExpanded = false;
				}
			});

			buttonContainer.appendChild(copyButton);
			buttonContainer.appendChild(expandButton);

			// Wrap the preElement with the new wrapper
			preElement.parentNode.insertBefore(wrapper, preElement);
			wrapper.appendChild(preElement);
			wrapper.insertBefore(buttonContainer, preElement); // Insert buttons inside wrapper, before pre
		}
	});
}

function styleButton(button) {
	button.style.padding = "0.25em 0.5em";
	button.style.border = "1px solid #555";
	button.style.borderRadius = "4px";
	button.style.backgroundColor = "#333";
	button.style.color = "#f1f1f1";
	button.style.fontSize = "0.8em";
	button.style.cursor = "pointer";
	// Hover effect
	button.onmouseover = () => (button.style.backgroundColor = "#444");
	button.onmouseout = () => (button.style.backgroundColor = "#333");
}

// Expose the function to be callable from other scripts if needed,
// though direct call after message append is also an option.
// window.initializeCodeBlockFeatures = initializeCodeBlockFeatures;

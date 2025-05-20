// static/chat/code_block_features.js

// SVG Icons
const svgIconCopy = `<svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em"><path d="M16 1H4c-1.1 0-2 .9-2 2v14h2V3h12V1zm3 4H8c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h11c1.1 0 2-.9 2-2V7c0-1.1-.9-2-2-2zm0 16H8V7h11v14z"></path></svg>`;
const svgIconCopiedCheck = `<svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em"><path d="M9 16.17L4.83 12l-1.42 1.41L9 19 21 7l-1.41-1.41L9 16.17z"></path></svg>`;
const svgIconExpand = `<svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"></path></svg>`;
const svgIconMinimize = `<svg viewBox="0 0 24 24" fill="currentColor" width="1em" height="1em"><path d="M5 16h3v3h2v-5H5v2zm3-8H5v2h5V5H8v3zm6 11h2v-3h3v-2h-5v5zm2-11V5h-2v5h5V8h-3z"></path></svg>`;

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
			copyButton.innerHTML = svgIconCopy; // Use SVG icon
			copyButton.title = "Copy code";
			copyButton.className = "code-block-copy-btn"; // Add a class for styling
			styleButton(copyButton);

			copyButton.addEventListener("click", () => {
				const codeContent = preElement.querySelector("code").innerText;
				navigator.clipboard
					.writeText(codeContent)
					.then(() => {
						copyButton.innerHTML = svgIconCopiedCheck; // Show checkmark
						copyButton.title = "Copied!";
						setTimeout(() => {
							copyButton.innerHTML = svgIconCopy; // Revert to copy icon
							copyButton.title = "Copy code";
						}, 2000);
					})
					.catch((err) => {
						console.error("Failed to copy text: ", err);
						copyButton.title = "Failed to copy";
						// Optionally provide user feedback for error
					});
			});

			// 2. Create Expand/Collapse Button
			const expandButton = document.createElement("button");
			expandButton.innerHTML = svgIconExpand; // Initial icon
			expandButton.title = "Expand code";
			expandButton.className = "code-block-expand-btn"; // Add a class for styling
			styleButton(expandButton);

			// Add a class to the pre element for default styling (e.g., max-height)
			preElement.classList.add("code-block-collapsible");

			// Explicitly set initial collapsed state via inline styles
			const collapsedHeight = "300px"; // Must match CSS .code-block-collapsible max-height
			preElement.style.maxHeight = collapsedHeight;
			preElement.style.overflowY = "auto"; // Allow vertical scroll in collapsed state
			preElement.style.overflowX = "auto"; // Allow horizontal scroll in collapsed state
			let isCurrentlyExpanded = false; // This tracks vertical expansion in normal mode, not used with canvas directly
			let isInCanvasMode = false; // New state for canvas mode

			const minimizeFromCanvasMode = () => {
				wrapper.classList.remove("code-block-wrapper-canvas-mode");
				document.body.classList.remove("code-canvas-backdrop-active");
				preElement.style.maxHeight = collapsedHeight;
				preElement.style.height = "";
				preElement.style.width = "";
				preElement.style.overflowY = "auto"; // Allow vertical scroll in collapsed state
				preElement.style.overflowX = "auto"; // Ensure horizontal scroll is also auto
				expandButton.innerHTML = svgIconExpand;
				expandButton.title = "Expand code";
				isInCanvasMode = false;
				isCurrentlyExpanded = false; // Reset this too
				document.removeEventListener("click", clickOutsideHandler, true);
			};

			const clickOutsideHandler = (event) => {
				if (isInCanvasMode && wrapper && !wrapper.contains(event.target)) {
					minimizeFromCanvasMode();
				}
			};

			expandButton.addEventListener("click", () => {
				if (!isInCanvasMode) {
					// Enter canvas mode
					wrapper.classList.add("code-block-wrapper-canvas-mode");
					document.body.classList.add("code-canvas-backdrop-active");
					preElement.style.maxHeight = "none";
					preElement.style.height = "100%";
					preElement.style.width = "100%";
					preElement.style.overflow = "auto";
					expandButton.innerHTML = svgIconMinimize;
					expandButton.title = "Minimize code";
					isInCanvasMode = true;
					isCurrentlyExpanded = true; // Implied by canvas mode
					// Add click outside listener AFTER a brief moment to avoid capturing the same click
					setTimeout(() => {
						document.addEventListener("click", clickOutsideHandler, true);
					}, 0);
				} else {
					// Minimize from canvas mode
					minimizeFromCanvasMode();
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
	button.style.padding = "0.25em"; // Adjusted for icons
	button.style.border = "1px solid #555";
	button.style.borderRadius = "4px";
	button.style.backgroundColor = "#333";
	button.style.color = "#f1f1f1"; // Icon color
	button.style.fontSize = "1em"; // Ensure icon size is controlled by svg width/height
	button.style.cursor = "pointer";
	button.style.lineHeight = "1"; // Helps align SVG
	button.style.display = "inline-flex"; // Helps center SVG
	button.style.alignItems = "center";
	button.style.justifyContent = "center";
	// Hover effect
	button.onmouseover = () => (button.style.backgroundColor = "#444");
	button.onmouseout = () => (button.style.backgroundColor = "#333");
}

// Expose the function to be callable from other scripts if needed,
// though direct call after message append is also an option.
// window.initializeCodeBlockFeatures = initializeCodeBlockFeatures;

// Common functions used across the application
document.addEventListener("DOMContentLoaded", function () {
	// Process existing markdown content
	document.querySelectorAll(".markdown-content").forEach((container) => {
		// First, ensure markdown is properly rendered
		const rawContent = container.textContent;
		if (rawContent && !container.querySelector("pre, p, ul, ol, blockquote")) {
			try {
				container.innerHTML = marked.parse(rawContent);
			} catch (e) {
				console.error("Failed to parse markdown:", e);
			}
		}

		// Then highlight code blocks
		container.querySelectorAll("pre code").forEach((block) => {
			hljs.highlightElement(block);
		});
	});

	// Apply styles to message containers
	document.querySelectorAll(".message-enter").forEach((msg) => {
		// Ensure proper backgrounds
		if (msg.querySelector(".w-7.h-7.rounded-sm.bg-\\[\\#11A27F\\]")) {
			msg.classList.add("bg-[#444654]");
		}
	});

	window.scrollTo({
		top: document.body.scrollHeight,
		behavior: "auto"
	});
});

// Common functions used across the application
document.addEventListener("DOMContentLoaded", function () {
	// Process existing markdown content
	document.querySelectorAll(".markdown-content").forEach((container) => {
		// Skip quiz-message, which should be rendered as raw HTML
		if (container.classList.contains("quiz-message")) return;
		const rawContent = container.textContent.trim();
		// If the content looks like HTML (starts with <div, <table, etc.), set as HTML
		if (/^\s*<\w+/.test(rawContent)) {
			container.innerHTML = rawContent;
		} else {
			container.innerHTML = marked.parse(rawContent);
			container.querySelectorAll("pre code").forEach((block) => {
				hljs.highlightElement(block);
			});
		}
	});

	// Apply styles to message containers
	document.querySelectorAll(".message-enter").forEach((msg) => {
		// Ensure proper backgrounds
		if (msg.querySelector(".w-7.h-7.rounded-sm.bg-\\[\\#11A27F\\]")) {
			msg.classList.add("");
		}
	});

	window.scrollTo({
		top: document.body.scrollHeight,
		behavior: "auto"
	});
});

// RAG and Diagram Mode Toggle Functionality

// Ensure these are declared globally or managed in a shared scope if needed by other modules directly.
// For now, this module will manage its own instance of these variables based on localStorage.
let isRAGActive = false; 
let isDiagramModeActive = false;

// appendSystemNotification is expected to be globally available from message_handler.js
// If not, this will cause an error. We might need a more robust way to share functions.

document.addEventListener("DOMContentLoaded", function () {
    // Load saved states from localStorage
    const savedRAGState = localStorage.getItem("ragModeActive");
    if (savedRAGState !== null) {
        isRAGActive = JSON.parse(savedRAGState);
        console.log("mode_toggles.js: Loaded RAG state:", isRAGActive);
    } else {
        localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive)); // Initialize if not found
    }

    const savedDiagramModeState = localStorage.getItem("diagramModeActive");
    if (savedDiagramModeState !== null) {
        isDiagramModeActive = JSON.parse(savedDiagramModeState);
        console.log("mode_toggles.js: Loaded diagram mode state:", isDiagramModeActive);
    } else {
        localStorage.setItem("diagramModeActive", JSON.stringify(isDiagramModeActive)); // Initialize if not found
    }

    const ragToggleButton = document.getElementById("rag-mode-toggle");
    const diagramModeToggleButton = document.getElementById("diagram-mode-toggle");

    // --- RAG Toggle Button Logic --- 
    if (ragToggleButton) {
        console.log("mode_toggles.js: Found RAG toggle button, initial state:", isRAGActive);

        const setActiveRAGStyles = () => {
            if (ragToggleButton.querySelector("svg")) {
                ragToggleButton.querySelector("svg").classList.remove("text-gray-400");
                ragToggleButton.querySelector("svg").classList.add("text-green-400");
                ragToggleButton.classList.add("bg-gray-800");
            }
        };

        const setInactiveRAGStyles = () => {
            if (ragToggleButton.querySelector("svg")) {
                ragToggleButton.querySelector("svg").classList.remove("text-green-400");
                ragToggleButton.querySelector("svg").classList.add("text-gray-400");
                ragToggleButton.classList.remove("bg-gray-800");
            }
        };

        if (isRAGActive) {
            setActiveRAGStyles();
        } else {
            setInactiveRAGStyles();
        }

        ragToggleButton.addEventListener("click", () => {
            isRAGActive = !isRAGActive;
            console.log("mode_toggles.js: Toggling RAG mode to:", isRAGActive);

            if (isRAGActive) {
                setActiveRAGStyles();
                if (isDiagramModeActive) { // If RAG becomes active, disable diagram mode
                    isDiagramModeActive = false;
                    updateDiagramModeToggleButtonStyle(); // Assumes this function is defined below
                    localStorage.setItem("diagramModeActive", JSON.stringify(isDiagramModeActive));
                }
            } else {
                setInactiveRAGStyles();
            }
            localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
            if (window.appendSystemNotification) {
                window.appendSystemNotification(`RAG mode is now ${isRAGActive ? "ACTIVE" : "INACTIVE"}.`, "info");
            } else {
                console.warn("appendSystemNotification not found when toggling RAG mode.");
            }
        });
    } else {
        console.warn("mode_toggles.js: RAG toggle button not found.");
    }

    // --- Diagram Mode Toggle Button Logic --- 
    function updateDiagramModeToggleButtonStyle() {
        if (!diagramModeToggleButton) return;
        if (isDiagramModeActive) {
            if (diagramModeToggleButton.querySelector("svg")) {
                diagramModeToggleButton.querySelector("svg").classList.remove("text-gray-400");
                diagramModeToggleButton.querySelector("svg").classList.add("text-blue-400");
                diagramModeToggleButton.classList.add("bg-gray-800");
            }
        } else {
            if (diagramModeToggleButton.querySelector("svg")) {
                diagramModeToggleButton.querySelector("svg").classList.remove("text-blue-400");
                diagramModeToggleButton.querySelector("svg").classList.add("text-gray-400");
                diagramModeToggleButton.classList.remove("bg-gray-800");
            }
        }
    }

    if (diagramModeToggleButton) {
        console.log("mode_toggles.js: Found diagram mode toggle, initial state:", isDiagramModeActive);
        updateDiagramModeToggleButtonStyle(); // Set initial style

        diagramModeToggleButton.addEventListener("click", () => {
            isDiagramModeActive = !isDiagramModeActive;
            console.log("mode_toggles.js: Toggling diagram mode to:", isDiagramModeActive);
            updateDiagramModeToggleButtonStyle();

            if (isDiagramModeActive) { // If Diagram Mode becomes active, disable RAG mode
                if (isRAGActive) {
                    isRAGActive = false;
                    // Need setInactiveRAGStyles to be accessible here or duplicate its logic
                    // For now, assuming it was defined above for RAG button and is in scope.
                    const ragButton = document.getElementById("rag-mode-toggle"); // Re-select or ensure availability
                    if (ragButton && ragButton.querySelector("svg")) {
                        ragButton.querySelector("svg").classList.remove("text-green-400");
                        ragButton.querySelector("svg").classList.add("text-gray-400");
                        ragButton.classList.remove("bg-gray-800");
                    }
                    localStorage.setItem("ragModeActive", JSON.stringify(isRAGActive));
                }
            }
            localStorage.setItem("diagramModeActive", JSON.stringify(isDiagramModeActive));
            if (window.appendSystemNotification) {
                window.appendSystemNotification(`Diagram mode is now ${isDiagramModeActive ? "ACTIVE" : "INACTIVE"}.`, "info");
            } else {
                console.warn("appendSystemNotification not found when toggling Diagram mode.");
            }
        });
    } else {
        console.warn("mode_toggles.js: Diagram mode toggle button not found.");
    }

    // Expose mode states globally if needed by chat.js for form submission
    // This is a temporary measure during refactoring.
    window.getIsRAGActive = () => isRAGActive;
    window.getIsDiagramModeActive = () => isDiagramModeActive;
}); 
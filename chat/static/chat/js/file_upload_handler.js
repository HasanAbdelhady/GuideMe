// File upload handling for the main chat input

document.addEventListener("DOMContentLoaded", function () {
    const fileInput = document.getElementById("file-input");
    const fileNameIndicator = document.getElementById("file-name");
    const clearFileButton = document.getElementById("clear-file");

    if (!fileInput || !fileNameIndicator || !clearFileButton) {
        console.warn("File input elements not found. File handling will be affected.");
        return;
    }

    function clearFileSelection() {
        fileInput.value = ""; // Clears the selected file
        fileNameIndicator.textContent = ""; // Clears the displayed file name
        clearFileButton.classList.add("hidden"); // Hides the clear button
    }
    // Make clearFileSelection globally available if it needs to be called from elsewhere
    window.clearFileSelection = clearFileSelection; 

    fileInput.addEventListener("change", () => {
        const file = fileInput.files[0];
        if (file) {
            fileNameIndicator.textContent = `Attached: ${file.name}`;
            clearFileButton.classList.remove("hidden");
        } else {
            // If no file is selected (e.g., user cancels the dialog), clear the selection
            clearFileSelection();
        }
    });

    clearFileButton.addEventListener("click", clearFileSelection);
}); 
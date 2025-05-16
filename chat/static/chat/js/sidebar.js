// Sidebar specific functionality
document.addEventListener("DOMContentLoaded", function () {
    const sidebarToggle = document.getElementById("sidebar-toggle");
    const sidebar = document.getElementById("sidebar");
    const mainContent = document.getElementById("main-content");
    const closeSidebarButton = document.getElementById("close-sidebar");

    if (!sidebarToggle || !sidebar || !mainContent || !closeSidebarButton) {
        console.warn("Sidebar elements not found. Sidebar functionality might be affected.");
        return;
    }

    let sidebarOpen = !sidebar.classList.contains("-translate-x-full"); // Initial state based on class

    function openSidebar() {
        sidebarOpen = true;
        sidebar.classList.remove("-translate-x-full");
        if (window.innerWidth >= 768) { // md breakpoint
            mainContent.classList.add("md:pl-64");
        }
        sidebarToggle.setAttribute("aria-expanded", "true");
    }

    function closeSidebar() {
        sidebarOpen = false;
        sidebar.classList.add("-translate-x-full");
        mainContent.classList.remove("md:pl-64");
        sidebarToggle.setAttribute("aria-expanded", "false");
    }

    sidebarToggle.addEventListener("click", (e) => {
        e.stopPropagation();
        if (sidebarOpen) {
            closeSidebar();
        } else {
            openSidebar();
        }
    });

    closeSidebarButton.addEventListener("click", (e) => {
        e.stopPropagation();
        closeSidebar();
    });

    // Click outside to close sidebar
    document.addEventListener("click", (e) => {
        const clickedSidebar = sidebar.contains(e.target);
        const clickedToggle = sidebarToggle.contains(e.target);

        if (sidebarOpen && !clickedSidebar && !clickedToggle) {
            closeSidebar();
        }
    });

    // Optional: Adjust sidebar based on window resize
    // Consider if mainContent padding needs to be responsive beyond md:pl-64
    // For example, on smaller screens, the sidebar might overlay content, not push it.
    // The current CSS uses fixed positioning and translation, pl-64 is for larger screens.
}); 
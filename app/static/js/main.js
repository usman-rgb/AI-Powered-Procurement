/**
 * ProcureAI - Client-side Helpers
 */

document.addEventListener("DOMContentLoaded", () => {
    // Smooth scrolling for anchor navigation links
    const navLinks = document.querySelectorAll(".sidebar-nav a[href^='#']");
    navLinks.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const targetId = link.getAttribute("href").substring(1);
            const targetEl = document.getElementById(targetId);
            if (targetEl) {
                targetEl.scrollIntoView({ behavior: "smooth", block: "start" });
                navLinks.forEach(l => l.classList.remove("active"));
                link.classList.add("active");
            }
        });
    });

    console.log("ProcureAI Dashboard initialized.");
});

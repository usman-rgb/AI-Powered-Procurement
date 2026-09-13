/**
 * Manager Profile Customization Controller (profile.js)
 * Manages live profile avatar preview, real-time authority card sync,
 * and asynchronous persistence via PATCH /api/user/profile.
 */

document.addEventListener("DOMContentLoaded", () => {
    // --------------------------------------------------------------------------
    // 1. DOM Elements
    // --------------------------------------------------------------------------
    const profileForm = document.getElementById("profileForm");
    const inputName = document.getElementById("inputName");
    const inputJobTitle = document.getElementById("inputJobTitle");
    const selectDepartment = document.getElementById("selectDepartment");
    const inputPhone = document.getElementById("inputPhone");
    const inputOfficeLocation = document.getElementById("inputOfficeLocation");
    const inputBio = document.getElementById("inputBio");
    const inputSpendingLimit = document.getElementById("inputSpendingLimit");
    const selectWarehouse = document.getElementById("selectWarehouse");
    const checkAutopilot = document.getElementById("checkAutopilot");
    const btnSaveProfile = document.getElementById("btnSaveProfile");
    const saveSpinner = document.getElementById("saveSpinner");
    const saveBtnText = document.getElementById("saveBtnText");
    const btnResetProfile = document.getElementById("btnResetProfile");

    // Snapshot Elements
    const avatarPreviewBadge = document.getElementById("avatarPreviewBadge");
    const displayUserName = document.getElementById("displayUserName");
    const displayUserJobTitle = document.getElementById("displayUserJobTitle");
    const displayUserDept = document.getElementById("displayUserDept");
    const displaySpendingLimit = document.getElementById("displaySpendingLimit");
    const displayWarehouse = document.getElementById("displayWarehouse");
    const displayAutopilot = document.getElementById("displayAutopilot");
    const displayOffice = document.getElementById("displayOffice");

    // Alert & Toasts
    const profileAlertBanner = document.getElementById("profileAlertBanner");
    const profileAlertIcon = document.getElementById("profileAlertIcon");
    const profileAlertMessage = document.getElementById("profileAlertMessage");
    const toastContainer = document.getElementById("toastContainer");

    // Store original values for reset
    const originalValues = {
        name: inputName.value,
        job_title: inputJobTitle.value,
        department: selectDepartment.value,
        phone: inputPhone.value,
        office_location: inputOfficeLocation.value,
        bio: inputBio.value,
        spending_limit: inputSpendingLimit.value,
        preferred_warehouse: selectWarehouse.value,
        ai_autopilot_enabled: checkAutopilot.checked
    };

    // --------------------------------------------------------------------------
    // 2. Helper Functions
    // --------------------------------------------------------------------------
    function calculateInitials(name) {
        if (!name) return "US";
        const parts = name.trim().split(/\s+/);
        if (parts.length === 1) return parts[0].substring(0, 2).toUpperCase();
        return (parts[0][0] + parts[1][0]).toUpperCase();
    }

    function formatCurrency(val) {
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 0
        }).format(val || 0);
    }

    function showToast(message, type = "success") {
        if (!toastContainer) return;
        const toast = document.createElement("div");
        toast.className = `toast toast-${type}`;
        const icons = { success: "✓", warning: "⚠️", danger: "⛔", info: "ℹ️" };
        toast.innerHTML = `<span>${icons[type] || "ℹ️"}</span><span>${message}</span>`;
        toastContainer.appendChild(toast);

        setTimeout(() => {
            toast.style.opacity = "0";
            toast.style.transform = "translateY(12px)";
            toast.style.transition = "all 0.3s ease";
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    function showAlert(message, type = "success") {
        if (!profileAlertBanner) return;
        profileAlertBanner.classList.remove("d-none", "alert-danger", "alert-success", "alert-warning", "alert-info");
        profileAlertBanner.classList.add(`alert-${type}`);
        const icons = { danger: "⛔", warning: "⚠️", success: "✓", info: "ℹ️" };
        profileAlertIcon.textContent = icons[type] || "✓";
        profileAlertMessage.textContent = message;
        profileAlertBanner.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }

    function hideAlert() {
        if (profileAlertBanner) profileAlertBanner.classList.add("d-none");
    }

    function setLoading(isLoading) {
        btnSaveProfile.disabled = isLoading;
        if (btnResetProfile) btnResetProfile.disabled = isLoading;
        if (isLoading) {
            saveSpinner.classList.remove("d-none");
            saveBtnText.textContent = "Saving Changes...";
            btnSaveProfile.style.opacity = "0.8";
        } else {
            saveSpinner.classList.add("d-none");
            saveBtnText.textContent = "💾 Save Profile & Preferences";
            btnSaveProfile.style.opacity = "1";
        }
    }

    // --------------------------------------------------------------------------
    // 3. Live Snapshot Previews on Input
    // --------------------------------------------------------------------------
    inputName.addEventListener("input", (e) => {
        const val = e.target.value.trim() || "Manager";
        displayUserName.textContent = val;
        const newInitials = calculateInitials(val);
        avatarPreviewBadge.textContent = newInitials;
    });

    inputJobTitle.addEventListener("input", (e) => {
        displayUserJobTitle.textContent = e.target.value.trim() || "Procurement Officer";
    });

    selectDepartment.addEventListener("change", (e) => {
        displayUserDept.textContent = e.target.value;
    });

    inputSpendingLimit.addEventListener("input", (e) => {
        const num = parseFloat(e.target.value) || 0;
        displaySpendingLimit.textContent = formatCurrency(num);
    });

    selectWarehouse.addEventListener("change", (e) => {
        displayWarehouse.textContent = e.target.value;
    });

    checkAutopilot.addEventListener("change", (e) => {
        displayAutopilot.textContent = e.target.checked ? "ENABLED" : "MANUAL";
        displayAutopilot.className = `snapshot-metric-value ${e.target.checked ? "text-amber" : "text-muted"}`;
    });

    inputOfficeLocation.addEventListener("input", (e) => {
        displayOffice.textContent = e.target.value.trim() || "HQ Tower";
    });

    // --------------------------------------------------------------------------
    // 4. Reset Form
    // --------------------------------------------------------------------------
    if (btnResetProfile) {
        btnResetProfile.addEventListener("click", () => {
            inputName.value = originalValues.name;
            inputJobTitle.value = originalValues.job_title;
            selectDepartment.value = originalValues.department;
            inputPhone.value = originalValues.phone;
            inputOfficeLocation.value = originalValues.office_location;
            inputBio.value = originalValues.bio;
            inputSpendingLimit.value = originalValues.spending_limit;
            selectWarehouse.value = originalValues.preferred_warehouse;
            checkAutopilot.checked = originalValues.ai_autopilot_enabled;

            // Trigger preview sync
            inputName.dispatchEvent(new Event("input"));
            inputJobTitle.dispatchEvent(new Event("input"));
            selectDepartment.dispatchEvent(new Event("change"));
            inputSpendingLimit.dispatchEvent(new Event("input"));
            selectWarehouse.dispatchEvent(new Event("change"));
            checkAutopilot.dispatchEvent(new Event("change"));
            inputOfficeLocation.dispatchEvent(new Event("input"));

            hideAlert();
            showToast("Form reset to saved profile values.", "info");
        });
    }

    // --------------------------------------------------------------------------
    // 5. Asynchronous Profile Submission (PATCH /api/user/profile)
    // --------------------------------------------------------------------------
    profileForm.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert();

        const name = inputName.value.trim();
        if (!name) {
            showAlert("Full corporate name cannot be blank.", "danger");
            inputName.focus();
            return;
        }

        const payload = {
            name: name,
            job_title: inputJobTitle.value.trim(),
            department: selectDepartment.value,
            phone: inputPhone.value.trim(),
            office_location: inputOfficeLocation.value.trim(),
            bio: inputBio.value.trim(),
            spending_limit: parseFloat(inputSpendingLimit.value) || 0,
            preferred_warehouse: selectWarehouse.value,
            ai_autopilot_enabled: checkAutopilot.checked
        };

        setLoading(true);

        try {
            const resp = await fetch("/api/user/profile", {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify(payload)
            });

            const result = await resp.json();

            if (resp.ok && result.success) {
                // Update cached original values
                Object.assign(originalValues, payload);

                const initials = calculateInitials(name);

                // Update global sidebar user card in base.html
                const sidebarName = document.querySelector(".sidebar .user-name");
                const sidebarTitle = document.querySelector(".sidebar .user-title");
                const sidebarAvatar = document.querySelector(".sidebar .user-avatar-badge");

                if (sidebarName) sidebarName.textContent = name;
                if (sidebarTitle) sidebarTitle.textContent = payload.department;
                if (sidebarAvatar) sidebarAvatar.textContent = initials;

                showToast("Manager profile and authority preferences updated!", "success");
                showAlert("Your profile changes and procurement preferences were successfully saved to Firestore.", "success");
            } else {
                showAlert(result.error || "Failed to update profile on server.", "danger");
                showToast(result.error || "Failed to save profile.", "danger");
            }
        } catch (err) {
            console.error("Profile save error:", err);
            showAlert(`Network communication error: ${err.message}`, "danger");
            showToast("Failed to connect to backend server.", "danger");
        } finally {
            setLoading(false);
        }
    });
});

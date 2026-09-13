/**
 * Purchase Request Form Handler (request_form.js)
 * Handles client-side validation, live total calculations, and AJAX submission to Flask.
 */

document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("purchaseRequestForm");
    if (!form) return;

    // Form inputs
    const itemNameInput = document.getElementById("itemName");
    const skuInput = document.getElementById("sku");
    const categorySelect = document.getElementById("category");
    const quantityInput = document.getElementById("quantity");
    const estimatedPriceInput = document.getElementById("estimatedPrice");
    const departmentSelect = document.getElementById("department");
    const requiredDateInput = document.getElementById("requiredDate");
    const prioritySelect = document.getElementById("priority");
    const requesterNameInput = document.getElementById("requesterName");
    const purposeTextarea = document.getElementById("purpose");

    // UI elements
    const totalDisplay = document.getElementById("calculatedTotalDisplay");
    const submitBtn = document.getElementById("btnSubmitRequest");
    const spinner = document.getElementById("btnSpinner");
    const btnText = document.getElementById("btnText");
    const alertBox = document.getElementById("formAlert");
    const alertTitle = document.getElementById("formAlertTitle");
    const alertMessage = document.getElementById("formAlertMessage");
    const alertIcon = document.getElementById("formAlertIcon");
    const alertActions = document.getElementById("formAlertActions");
    const btnReset = document.getElementById("btnResetForm");

    // Set minimum date for requiredDate to today
    const today = new Date().toISOString().split("T")[0];
    if (requiredDateInput) {
        requiredDateInput.min = today;
    }

    // --------------------------------------------------------------------------
    // 1. Live Total Price Calculation
    // --------------------------------------------------------------------------
    function updateCalculatedTotal() {
        const qty = parseInt(quantityInput.value, 10) || 0;
        const price = parseFloat(estimatedPriceInput.value) || 0.0;
        const total = Math.max(0, qty * price);

        totalDisplay.textContent = new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
        }).format(total);
    }

    quantityInput.addEventListener("input", updateCalculatedTotal);
    estimatedPriceInput.addEventListener("input", updateCalculatedTotal);

    // --------------------------------------------------------------------------
    // 2. Field Validation Helpers
    // --------------------------------------------------------------------------
    function setFieldError(inputEl, feedbackId, message) {
        inputEl.classList.add("is-invalid");
        inputEl.classList.remove("is-valid");
        const feedbackEl = document.getElementById(feedbackId);
        if (feedbackEl) {
            feedbackEl.textContent = message;
        }
    }

    function clearFieldError(inputEl, feedbackId) {
        inputEl.classList.remove("is-invalid");
        inputEl.classList.add("is-valid");
        const feedbackEl = document.getElementById(feedbackId);
        if (feedbackEl) {
            feedbackEl.textContent = "";
        }
    }

    // Auto-clear invalid state on user interaction
    [
        [itemNameInput, "itemNameFeedback"],
        [skuInput, "skuFeedback"],
        [categorySelect, "categoryFeedback"],
        [quantityInput, "quantityFeedback"],
        [estimatedPriceInput, "estimatedPriceFeedback"],
        [departmentSelect, "departmentFeedback"],
        [requiredDateInput, "requiredDateFeedback"],
        [purposeTextarea, "purposeFeedback"],
    ].forEach(([el, feedbackId]) => {
        if (!el) return;
        el.addEventListener("input", () => {
            if (el.classList.contains("is-invalid")) {
                clearFieldError(el, feedbackId);
            }
        });
        el.addEventListener("change", () => {
            if (el.classList.contains("is-invalid")) {
                clearFieldError(el, feedbackId);
            }
        });
    });

    function validateForm() {
        let isValid = true;
        let firstInvalidField = null;

        // Item Name validation
        const itemName = itemNameInput.value.trim();
        if (!itemName) {
            setFieldError(itemNameInput, "itemNameFeedback", "Item or service name is required.");
            isValid = false;
            firstInvalidField = firstInvalidField || itemNameInput;
        } else if (itemName.length < 3) {
            setFieldError(itemNameInput, "itemNameFeedback", "Item name must be at least 3 characters.");
            isValid = false;
            firstInvalidField = firstInvalidField || itemNameInput;
        } else {
            clearFieldError(itemNameInput, "itemNameFeedback");
        }

        // SKU validation
        const sku = skuInput.value.trim();
        if (!sku) {
            setFieldError(skuInput, "skuFeedback", "SKU or Item Code is required.");
            isValid = false;
            firstInvalidField = firstInvalidField || skuInput;
        } else {
            clearFieldError(skuInput, "skuFeedback");
        }

        // Category validation
        if (!categorySelect.value) {
            setFieldError(categorySelect, "categoryFeedback", "Please select a category.");
            isValid = false;
            firstInvalidField = firstInvalidField || categorySelect;
        } else {
            clearFieldError(categorySelect, "categoryFeedback");
        }

        // Quantity validation
        const quantity = parseInt(quantityInput.value, 10);
        if (isNaN(quantity) || quantity < 1) {
            setFieldError(quantityInput, "quantityFeedback", "Quantity must be at least 1 unit.");
            isValid = false;
            firstInvalidField = firstInvalidField || quantityInput;
        } else {
            clearFieldError(quantityInput, "quantityFeedback");
        }

        // Estimated Price validation
        const price = parseFloat(estimatedPriceInput.value);
        if (isNaN(price) || price <= 0) {
            setFieldError(estimatedPriceInput, "estimatedPriceFeedback", "Estimated price must be greater than $0.00.");
            isValid = false;
            firstInvalidField = firstInvalidField || estimatedPriceInput;
        } else {
            clearFieldError(estimatedPriceInput, "estimatedPriceFeedback");
        }

        // Department validation
        if (!departmentSelect.value) {
            setFieldError(departmentSelect, "departmentFeedback", "Please select a requesting department.");
            isValid = false;
            firstInvalidField = firstInvalidField || departmentSelect;
        } else {
            clearFieldError(departmentSelect, "departmentFeedback");
        }

        // Required Date validation
        const reqDate = requiredDateInput.value;
        if (!reqDate) {
            setFieldError(requiredDateInput, "requiredDateFeedback", "Required delivery date is mandatory.");
            isValid = false;
            firstInvalidField = firstInvalidField || requiredDateInput;
        } else if (new Date(reqDate) < new Date(today)) {
            setFieldError(requiredDateInput, "requiredDateFeedback", "Date cannot be in the past.");
            isValid = false;
            firstInvalidField = firstInvalidField || requiredDateInput;
        } else {
            clearFieldError(requiredDateInput, "requiredDateFeedback");
        }

        // Purpose validation
        const purpose = purposeTextarea.value.trim();
        if (!purpose) {
            setFieldError(purposeTextarea, "purposeFeedback", "Business purpose and justification is required.");
            isValid = false;
            firstInvalidField = firstInvalidField || purposeTextarea;
        } else if (purpose.length < 10) {
            setFieldError(purposeTextarea, "purposeFeedback", "Please provide a more descriptive justification (min 10 characters).");
            isValid = false;
            firstInvalidField = firstInvalidField || purposeTextarea;
        } else {
            clearFieldError(purposeTextarea, "purposeFeedback");
        }

        if (firstInvalidField) {
            firstInvalidField.focus();
        }

        return isValid;
    }

    // --------------------------------------------------------------------------
    // 3. UI Alert Banner Helpers
    // --------------------------------------------------------------------------
    function showAlert(type, title, message, showActions = false) {
        alertBox.className = `banner banner-${type}`;
        alertTitle.textContent = title;
        alertMessage.innerHTML = message;
        alertIcon.textContent = type === "success" ? "✓" : "⚠️";
        
        if (showActions) {
            alertActions.classList.remove("d-none");
        } else {
            alertActions.classList.add("d-none");
        }
        alertBox.classList.remove("d-none");
        alertBox.scrollIntoView({ behavior: "smooth", block: "start" });
    }

    function hideAlert() {
        alertBox.classList.add("d-none");
    }

    // --------------------------------------------------------------------------
    // 4. Form Submission via Fetch API
    // --------------------------------------------------------------------------
    form.addEventListener("submit", async (e) => {
        e.preventDefault();
        hideAlert();

        if (!validateForm()) {
            return;
        }

        // Set Loading State
        submitBtn.disabled = true;
        spinner.classList.remove("d-none");
        btnText.textContent = "Validating & Submitting...";

        // Construct Payload
        const payload = {
            item_name: itemNameInput.value.trim(),
            sku: skuInput.value.trim(),
            category: categorySelect.value,
            quantity: parseInt(quantityInput.value, 10),
            estimated_price: parseFloat(estimatedPriceInput.value),
            required_date: requiredDateInput.value,
            department: departmentSelect.value,
            purpose: purposeTextarea.value.trim(),
            priority: prioritySelect ? prioritySelect.value : "medium",
            requester_name: requesterNameInput ? requesterNameInput.value.trim() : "",
        };

        try {
            const response = await fetch("/api/submit_request", {
                method: "POST",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                body: JSON.stringify(payload),
            });

            const data = await response.json();

            if (response.ok && data.success) {
                const prId = data.pr_id || (data.data && data.data.request_id) || "N/A";
                const total = new Intl.NumberFormat("en-US", {
                    style: "currency",
                    currency: "USD",
                }).format(data.data?.total_amount || (payload.quantity * payload.estimated_price));

                showAlert(
                    "success",
                    "Purchase Request Submitted Successfully!",
                    `Request ID <strong class="font-mono text-primary">${prId}</strong> has been logged to Firebase with status 
                    <span class="badge badge-warning">Pending Validation</span> for ${total}. Automated AI compliance screening is underway.`,
                    true
                );

                // Disable form inputs to prevent double submission
                form.querySelectorAll("input, select, textarea, button[type='submit']").forEach(el => {
                    el.disabled = true;
                });
            } else {
                const errorMsg = data.error || data.message || "Failed to submit purchase request.";
                showAlert(
                    "warning",
                    "Submission Notice",
                    `${errorMsg}`
                );
            }
        } catch (err) {
            console.error("Submission error:", err);
            showAlert(
                "warning",
                "Network Error",
                `Unable to communicate with the procurement service: ${err.message}. Please check if the Flask server is running.`
            );
        } finally {
            // Restore button state
            submitBtn.disabled = false;
            spinner.classList.add("d-none");
            btnText.textContent = "Submit Purchase Request";
        }
    });

    // --------------------------------------------------------------------------
    // 5. Reset Form Handler
    // --------------------------------------------------------------------------
    if (btnReset) {
        btnReset.addEventListener("click", () => {
            form.reset();
            form.querySelectorAll("input, select, textarea, button").forEach(el => {
                el.disabled = false;
                el.classList.remove("is-valid", "is-invalid");
            });
            updateCalculatedTotal();
            hideAlert();
            itemNameInput.focus();
        });
    }

    // Initialize total display
    updateCalculatedTotal();
});

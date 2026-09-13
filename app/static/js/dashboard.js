/**
 * Purchase Manager Dashboard & Explainable AI Modal (dashboard.js)
 * Fetches requests from Flask API, renders interactive data table,
 * manages the Explainable AI Decision Modal with Circular SVG Gauge,
 * and handles one-click Manager action approvals via PATCH API.
 */

document.addEventListener("DOMContentLoaded", () => {
    // State management
    let allRequests = [];
    let currentFilter = "ALL";
    let activeModalRequestId = null;

    // DOM Elements - Metrics
    const metricTotal = document.getElementById("metricTotalRequests");
    const metricPending = document.getElementById("metricPendingRequests");
    const metricApproved = document.getElementById("metricApprovedRequests");
    const metricSavings = document.getElementById("metricIdentifiedSavings");

    // DOM Elements - Table & Controls
    const tableBody = document.getElementById("requestsTableBody");
    const searchInput = document.getElementById("searchTableInput");
    const filterPills = document.querySelectorAll("#statusFilterPills .filter-pill");
    const btnRefresh = document.getElementById("btnRefreshTable");

    // DOM Elements - Modal
    const modal = document.getElementById("aiModal");
    const btnModalClose = document.getElementById("btnModalClose");
    const btnModalFooterClose = document.getElementById("btnModalFooterClose");
    const modalRequestId = document.getElementById("modalRequestId");
    const modalItemTitle = document.getElementById("modalItemTitle");
    const modalMetaSubtitle = document.getElementById("modalMetaSubtitle");
    const aiDecisionBanner = document.getElementById("aiDecisionBanner");
    const modalDecisionBadge = document.getElementById("modalDecisionBadge");
    const modalAiSource = document.getElementById("modalAiSource");
    const modalSavingsContainer = document.getElementById("modalSavingsContainer");
    const modalSavingsVal = document.getElementById("modalSavingsVal");
    const modalCriticalityScore = document.getElementById("modalCriticalityScore");
    const gaugeCircle = document.getElementById("gaugeCircle");
    const modalPriorityBadge = document.getElementById("modalPriorityBadge");
    const modalReasoningText = document.getElementById("modalReasoningText");
    const modalCurrentStatus = document.getElementById("modalCurrentStatus");

    // DOM Elements - Action Buttons
    const btnActionApprove = document.getElementById("btnActionApprove");
    const btnActionHold = document.getElementById("btnActionHold");
    const btnActionInvestigate = document.getElementById("btnActionInvestigate");
    const btnActionReject = document.getElementById("btnActionReject");

    const toastContainer = document.getElementById("toastContainer");

    // Format Currency Helper
    const formatCurrency = (val) => {
        return new Intl.NumberFormat("en-US", {
            style: "currency",
            currency: "USD",
            maximumFractionDigits: 0
        }).format(val || 0);
    };

    // --------------------------------------------------------------------------
    // 1. Toast Notification Helper
    // --------------------------------------------------------------------------
    function showToast(message, type = "info") {
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

    // --------------------------------------------------------------------------
    // 2. Fetch Requests from Flask API
    // --------------------------------------------------------------------------
    async function loadRequests() {
        try {
            const resp = await fetch("/api/procurement/requests?limit=100");
            const result = await resp.json();

            if (resp.ok && result.success) {
                allRequests = result.data || [];
                updateMetrics(allRequests);
                renderTable();
            } else {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="8" class="empty-cell text-danger">
                            Failed to load purchase requests: ${result.error || "Unknown error"}
                        </td>
                    </tr>
                `;
            }
        } catch (err) {
            console.error("Error fetching requests:", err);
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="empty-cell text-danger">
                        Unable to load purchase requests. Please verify connectivity and refresh.
                    </td>
                </tr>
            `;
        }
    }

    // --------------------------------------------------------------------------
    // 3. Update Summary KPI Metrics
    // --------------------------------------------------------------------------
    function updateMetrics(data) {
        metricTotal.textContent = data.length;

        const pending = data.filter(r => {
            const s = (r.status || "").toLowerCase();
            return s === "submitted" || s === "pending validation" || s === "draft" || s.includes("action required");
        }).length;
        metricPending.textContent = pending;

        const approved = data.filter(r => {
            const s = (r.status || "").toLowerCase();
            return s === "approved" || s === "approved by ai" || s === "fulfilled";
        }).length;
        metricApproved.textContent = approved;

        // Sum identified AI savings across all evaluated requests
        const totalSavings = data.reduce((acc, r) => {
            const s = r.ai_decision ? (parseFloat(r.ai_decision.Estimated_Savings) || 0) : 0;
            return acc + s;
        }, 0);
        metricSavings.textContent = formatCurrency(totalSavings);
    }

    // --------------------------------------------------------------------------
    // 4. Render Table with Search and Status Filtering
    // --------------------------------------------------------------------------
    function renderTable() {
        const query = searchInput.value.trim().toLowerCase();

        const filtered = allRequests.filter(req => {
            // Filter pill matching
            const status = (req.status || "").toLowerCase();
            if (currentFilter === "PENDING" && !(status === "submitted" || status === "pending validation" || status.includes("action required"))) {
                return false;
            }
            if (currentFilter === "APPROVED" && !(status === "approved" || status === "approved by ai" || status === "fulfilled")) {
                return false;
            }
            if (currentFilter === "HOLD" && !(status === "hold" || status === "on_hold" || status.includes("hold"))) {
                return false;
            }
            if (currentFilter === "REJECTED" && !(status === "rejected" || status === "rejected by ai" || status === "cancelled")) {
                return false;
            }

            // Search query matching
            if (query) {
                const title = (req.title || "").toLowerCase();
                const id = (req.request_id || "").toLowerCase();
                const dept = (req.department || "").toLowerCase();
                const user = (req.requester_name || "").toLowerCase();
                const sku = (req.items && req.items[0]?.sku || "").toLowerCase();
                return title.includes(query) || id.includes(query) || dept.includes(query) || user.includes(query) || sku.includes(query);
            }

            return true;
        });

        if (filtered.length === 0) {
            const isFiltering = currentFilter !== "ALL" || Boolean(query);
            tableBody.innerHTML = `
                <tr>
                    <td colspan="8" class="empty-cell py-8">
                        <div style="padding: 2.5rem 1rem; text-align: center;">
                            <div style="font-size: 2rem; margin-bottom: 0.5rem; opacity: 0.7;">📋</div>
                            <div style="font-size: 1rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.35rem;">
                                ${isFiltering ? "No matching purchase requests found" : "No purchase requests logged yet"}
                            </div>
                            <p style="font-size: 0.85rem; color: var(--text-secondary); max-width: 420px; margin: 0 auto 1.25rem auto;">
                                ${isFiltering ? "Try clearing your search keyword or switching the status filter tab." : "Create your first requisition to start AI risk screening, multi-warehouse stock checks, and managerial approvals."}
                            </p>
                            ${!isFiltering ? `
                                <a href="/submit-request" class="btn btn-sm btn-primary">
                                    <span>➕</span> Submit Your First Request
                                </a>
                            ` : ''}
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tableBody.innerHTML = filtered.map(req => {
            const firstItem = req.items && req.items.length > 0 ? req.items[0] : {};
            const sku = firstItem.sku || "N/A";
            const qty = firstItem.quantity || req.quantity || 1;
            const amount = formatCurrency(req.total_amount);

            // Format Status Badge
            const status = req.status || "submitted";
            let statusBadge = `<span class="badge badge-secondary">${status}</span>`;
            const sLower = status.toLowerCase();
            if (sLower.includes("approved")) statusBadge = `<span class="badge badge-success">${status}</span>`;
            else if (sLower.includes("rejected")) statusBadge = `<span class="badge badge-danger">${status}</span>`;
            else if (sLower.includes("hold")) statusBadge = `<span class="badge badge-warning">${status}</span>`;
            else if (sLower.includes("action required")) statusBadge = `<span class="badge badge-warning">Action Req.</span>`;
            else if (sLower.includes("pending") || sLower === "submitted") statusBadge = `<span class="badge badge-warning">Pending</span>`;

            // Format AI Decision Pill
            const aiDec = req.ai_decision ? (req.ai_decision.Decision || "").toUpperCase() : null;
            let aiPill = `<span class="ai-decision-pill ai-pill-pending">Pending AI</span>`;
            if (aiDec === "APPROVE") {
                aiPill = `<span class="ai-decision-pill ai-pill-approve">✓ APPROVE</span>`;
            } else if (aiDec === "REDUCE") {
                aiPill = `<span class="ai-decision-pill ai-pill-reduce">✂ REDUCE</span>`;
            } else if (aiDec === "HOLD") {
                aiPill = `<span class="ai-decision-pill ai-pill-hold">⏸ HOLD</span>`;
            } else if (aiDec === "REJECT") {
                aiPill = `<span class="ai-decision-pill ai-pill-reject">⛔ REJECT</span>`;
            }

            return `
                <tr data-request-id="${req.request_id}">
                    <td class="font-mono text-primary font-bold">${req.request_id}</td>
                    <td>
                        <div class="table-title">${req.title || firstItem.item_name || "Purchase Request"}</div>
                        <div class="table-subtitle font-mono">${sku} • ${qty} units</div>
                    </td>
                    <td><span class="badge badge-light">${req.department || "General"}</span></td>
                    <td>${req.requester_name || req.requester_id || "Employee"}</td>
                    <td class="font-bold font-mono">${amount}</td>
                    <td>${statusBadge}</td>
                    <td>${aiPill}</td>
                    <td class="text-right">
                        <div class="row-actions-group">
                            <button 
                                type="button" 
                                class="btn-row-action btn-row-approve" 
                                title="${sLower.includes('approved') ? 'Already Approved' : 'Quick Approve Requisition'}" 
                                aria-label="Approve Request"
                                onclick="window.quickApproveRequest('${req.request_id}', this)"
                                ${sLower.includes('approved') ? 'disabled' : ''}
                            >
                                <span class="btn-icon">✓</span>
                            </button>
                            <button 
                                type="button" 
                                class="btn-row-action btn-row-reject" 
                                title="${sLower.includes('rejected') ? 'Already Rejected' : 'Quick Reject Requisition'}" 
                                aria-label="Reject Request"
                                onclick="window.quickRejectRequest('${req.request_id}', this)"
                                ${sLower.includes('rejected') ? 'disabled' : ''}
                            >
                                <span class="btn-icon">✕</span>
                            </button>
                            <button 
                                type="button" 
                                class="btn-row-action btn-row-inspect" 
                                title="${req.ai_decision ? 'Inspect AI Decision & Reasoning' : 'Run AI Screening'}" 
                                aria-label="Inspect AI Decision"
                                onclick="${req.ai_decision ? `window.openAIMDecisionModal('${req.request_id}')` : `window.triggerAIDecision('${req.request_id}')`}"
                            >
                                <span class="btn-icon">👁</span>
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    // --------------------------------------------------------------------------
    // 5. Explainable AI Modal Operations
    // --------------------------------------------------------------------------
    window.openAIMDecisionModal = function(requestId) {
        const req = allRequests.find(r => r.request_id === requestId);
        if (!req) return;

        activeModalRequestId = requestId;
        const ai = req.ai_decision || {};
        const vr = req.validation_report || {};
        const layers = vr.layers || {};

        modalRequestId.textContent = req.request_id;
        modalItemTitle.textContent = req.title || "Purchase Requisition";
        modalMetaSubtitle.textContent = `${req.department} • Requested by ${req.requester_name || req.requester_id || "Employee"} • Total: ${formatCurrency(req.total_amount)}`;
        modalCurrentStatus.textContent = req.status || "Pending Validation";

        // Decision Banner & Color Highlights
        const decision = (ai.Decision || "HOLD").toUpperCase();
        modalDecisionBadge.textContent = decision;
        aiDecisionBanner.className = `ai-decision-banner banner-${decision.toLowerCase()}`;
        modalAiSource.textContent = "ProcureAI Enterprise Intelligence";

        // Savings Tag
        const savings = parseFloat(ai.Estimated_Savings) || 0;
        if (savings > 0) {
            modalSavingsContainer.classList.remove("d-none");
            modalSavingsVal.textContent = formatCurrency(savings);
        } else {
            modalSavingsContainer.classList.add("d-none");
        }

        // Circular Gauge - Criticality Score (0 to 100)
        const score = Math.max(1, Math.min(100, parseInt(ai.Criticality_Score) || 50));
        modalCriticalityScore.textContent = score;

        // Animate SVG circle stroke dashoffset (circumference = 2 * pi * 42 = ~264)
        const circumference = 264;
        const offset = circumference - (circumference * score / 100);
        gaugeCircle.style.strokeDashoffset = offset;

        if (score <= 40) {
            gaugeCircle.style.stroke = "var(--success)";
        } else if (score <= 70) {
            gaugeCircle.style.stroke = "var(--warning)";
        } else {
            gaugeCircle.style.stroke = "var(--danger)";
        }

        // Priority Badge
        const priority = (ai.Priority_Level || "MEDIUM").toUpperCase();
        modalPriorityBadge.textContent = priority;
        if (priority === "CRITICAL") modalPriorityBadge.className = "badge badge-danger";
        else if (priority === "HIGH") modalPriorityBadge.className = "badge badge-warning";
        else if (priority === "MEDIUM") modalPriorityBadge.className = "badge badge-info";
        else modalPriorityBadge.className = "badge badge-success";

        // AI Reasoning text
        modalReasoningText.textContent = ai.Reasoning || "Automated evaluation generated based on deterministic supply chain rules and policies.";

        // Populate 4 Validation Layers
        populateLayerCard(
            "l1",
            layers.layer1_budget,
            "Budget Verified",
            (d) => `Remaining: ${formatCurrency(d.remaining_amount)} • Allocated: ${formatCurrency(d.allocated_amount)}`
        );
        populateLayerCard(
            "l2",
            layers.layer2_warehouse_stock,
            "Internal Stock",
            (d) => {
                if (d.idle_locations && d.idle_locations.length > 0) {
                    return d.idle_locations.map(l => `${l.location_name}: ${l.available_stock}u`).join(", ");
                }
                return "Zero idle units across hubs.";
            }
        );
        populateLayerCard(
            "l3",
            layers.layer3_duplicate_check,
            "Duplicate Check",
            (d) => `${d.duplicate_count || 0} overlapping request(s) in last 30 days.`
        );
        populateLayerCard(
            "l4",
            layers.layer4_historical_usage,
            "Consumption Rate",
            (d) => `Monthly avg: ${d.avg_monthly_consumption || 0}u • Spike: ${d.spike_ratio ? d.spike_ratio + "x" : "N/A"}`
        );

        resetActionButtons(req.status);
        modal.classList.remove("d-none");
    };

    function populateLayerCard(prefix, layerData, defaultTitle, detailsFormatter) {
        const headlineEl = document.getElementById(`${prefix}Headline`);
        const badgeEl = document.getElementById(`${prefix}Badge`);
        const msgEl = document.getElementById(`${prefix}Msg`);
        const detailsEl = document.getElementById(`${prefix}Details`);

        if (!layerData) {
            headlineEl.textContent = defaultTitle;
            badgeEl.textContent = "PASSED";
            badgeEl.className = "badge badge-success";
            msgEl.textContent = "No validation flags triggered.";
            detailsEl.textContent = "";
            return;
        }

        headlineEl.textContent = layerData.title || defaultTitle;
        const status = (layerData.status || "PASSED").toUpperCase();
        badgeEl.textContent = status;

        if (status === "PASSED") badgeEl.className = "badge badge-success";
        else if (status === "WARNING") badgeEl.className = "badge badge-warning";
        else badgeEl.className = "badge badge-danger";

        msgEl.textContent = layerData.message || "-";
        if (layerData.details && detailsFormatter) {
            detailsEl.textContent = detailsFormatter(layerData.details);
        } else {
            detailsEl.textContent = "";
        }
    }

    // Close Modal
    function closeModal() {
        modal.classList.add("d-none");
        activeModalRequestId = null;
        resetActionButtons();
    }
    btnModalClose.addEventListener("click", closeModal);
    if (btnModalFooterClose) btnModalFooterClose.addEventListener("click", closeModal);
    modal.addEventListener("click", (e) => {
        if (e.target === modal) closeModal();
    });
    document.addEventListener("keydown", (e) => {
        if (e.key === "Escape" && !modal.classList.contains("d-none")) {
            closeModal();
        }
    });

    // --------------------------------------------------------------------------
    // 6. Trigger AI Decision via API
    // --------------------------------------------------------------------------
    window.triggerAIDecision = async function(requestId) {
        showToast(`Evaluating purchase request ${requestId} with AI Decision Engine...`, "info");

        try {
            const resp = await fetch(`/api/ai_decision/${requestId}`, { method: "POST" });
            const data = await resp.json();

            if (resp.ok && data.success) {
                showToast(`AI Decision Complete: ${data.ai_decision.Decision}`, "success");
                // Update item in local list
                const index = allRequests.findIndex(r => r.request_id === requestId);
                if (index !== -1) {
                    allRequests[index].ai_decision = data.ai_decision;
                    allRequests[index].status = data.new_status;
                    allRequests[index].validation_report = data.validation_report;
                }
                updateMetrics(allRequests);
                renderTable();
                window.openAIMDecisionModal(requestId);
            } else {
                showToast(`AI evaluation failed: ${data.error || "Unknown error"}`, "danger");
            }
        } catch (err) {
            showToast(`API call failed: ${err.message}`, "danger");
        }
    };

    // --------------------------------------------------------------------------
    // 7. Purchase Manager Action Handlers (Approve, Hold, Investigate, Reject)
    // --------------------------------------------------------------------------
    function resetActionButtons(status = "") {
        const s = (status || "").toLowerCase();

        btnActionApprove.disabled = false;
        btnActionApprove.innerHTML = s.includes("approved") ? '<span>✓</span> Approved' : '<span>✓</span> Approve';
        btnActionApprove.style.opacity = "1";

        btnActionHold.disabled = false;
        btnActionHold.innerHTML = s.includes("hold") ? '<span>⏸</span> On Hold' : '<span>⏸</span> Hold';
        btnActionHold.style.opacity = "1";

        btnActionInvestigate.disabled = false;
        btnActionInvestigate.innerHTML = s.includes("investigating") ? '<span>🔎</span> Investigating' : '<span>🔎</span> Investigate';
        btnActionInvestigate.style.opacity = "1";

        btnActionReject.disabled = false;
        btnActionReject.innerHTML = s.includes("rejected") ? '<span>⛔</span> Rejected' : '<span>⛔</span> Reject';
        btnActionReject.style.opacity = "1";
    }

    async function updateRequestStatus(newStatus, actionLabel, targetBtn, overrideBudget = false) {
        if (!activeModalRequestId) return;
        const requestId = activeModalRequestId;

        // Visual loading state on action buttons
        const allBtns = [btnActionApprove, btnActionHold, btnActionInvestigate, btnActionReject];
        allBtns.forEach(b => { b.disabled = true; b.style.opacity = "0.7"; });
        if (targetBtn) {
            targetBtn.innerHTML = '<span class="loading-spinner-sm"></span> Updating...';
        }

        try {
            const resp = await fetch(`/api/procurement/requests/${requestId}/status`, {
                method: "PATCH",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    status: newStatus,
                    actor_id: overrideBudget ? "Procurement Director (Override)" : "Purchase Manager",
                    comment: overrideBudget
                        ? "Executive Overdraft Override approved via Decision Center."
                        : `Action '${actionLabel}' recorded via Purchase Manager AI Decision Center.`,
                    override_budget: overrideBudget
                })
            });

            const data = await resp.json();

            if (resp.ok && data.success) {
                if (targetBtn) {
                    targetBtn.innerHTML = `<span>✓</span> ${actionLabel}d!`;
                }
                modalCurrentStatus.textContent = newStatus;

                // Update local model
                const item = allRequests.find(r => r.request_id === requestId);
                if (item) {
                    item.status = newStatus;
                }
                updateMetrics(allRequests);
                renderTable();

                const successMsg = overrideBudget
                    ? `Request ${requestId} approved with Executive Overdraft Override!`
                    : `Request ${requestId} status successfully updated to '${newStatus}'!`;
                showToast(successMsg, "success");

                // Auto-close modal after brief confirmation
                setTimeout(() => {
                    closeModal();
                    const row = document.querySelector(`tr[data-request-id="${requestId}"]`);
                    if (row) {
                        row.scrollIntoView({ behavior: "smooth", block: "nearest" });
                        row.style.transition = "background-color 0.4s ease";
                        row.style.backgroundColor = "rgba(16, 185, 129, 0.25)";
                        setTimeout(() => {
                            row.style.backgroundColor = "";
                        }, 2000);
                    }
                }, 500);
            } else if (!resp.ok && (data.requires_override || (data.error && data.error.includes("Budget overcommit")))) {
                resetActionButtons();
                const confirmOverride = confirm(
                    `⚠️ Budget Headroom Warning:\n\n${data.error}\n\nDo you want to authorize an Executive Manager Override to approve this requisition?`
                );
                if (confirmOverride) {
                    return updateRequestStatus("approved", "Approve (Override)", targetBtn, true);
                } else {
                    showToast(`Approval halted: Department budget limit exceeded.`, "warning");
                }
            } else {
                showToast(`Failed to update status: ${data.error || "Server error"}`, "danger");
                resetActionButtons();
            }
        } catch (err) {
            showToast(`Network error updating status: ${err.message}`, "danger");
            resetActionButtons();
        }
    }

    btnActionApprove.addEventListener("click", () => updateRequestStatus("approved", "Approve", btnActionApprove));
    btnActionHold.addEventListener("click", () => updateRequestStatus("hold", "Hold", btnActionHold));
    btnActionInvestigate.addEventListener("click", () => updateRequestStatus("investigating", "Investigate", btnActionInvestigate));
    btnActionReject.addEventListener("click", () => updateRequestStatus("rejected", "Reject", btnActionReject));

    // --------------------------------------------------------------------------
    // 7b. Table Row Quick-Action Handlers (Inline Approve & Reject)
    // --------------------------------------------------------------------------
    window.quickApproveRequest = async function(requestId, btnEl, overrideBudget = false) {
        if (!requestId) return;
        const originalHtml = btnEl ? btnEl.innerHTML : '<span class="btn-icon">✓</span>';
        const row = btnEl ? btnEl.closest("tr") : document.querySelector(`tr[data-request-id="${requestId}"]`);

        // Disable all quick buttons in this row and show micro loading state
        if (row) {
            row.querySelectorAll(".btn-row-action").forEach(b => {
                b.disabled = true;
                b.style.opacity = "0.5";
            });
        }
        if (btnEl) {
            btnEl.innerHTML = '<span class="btn-spinner-xs"></span>';
        }

        try {
            const resp = await fetch(`/api/procurement/requests/${requestId}/status`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    status: "approved",
                    actor_id: overrideBudget ? "Procurement Director (Override)" : "Purchase Manager",
                    comment: overrideBudget
                        ? "Approved via table quick-action with Executive Overdraft Override."
                        : "Approved via table quick-action.",
                    override_budget: overrideBudget
                })
            });

            const data = await resp.json();

            if (resp.ok && data.success) {
                const toastMsg = overrideBudget
                    ? `Request ${requestId} approved with Executive Overdraft Override!`
                    : `Request ${requestId} approved successfully!`;
                showToast(toastMsg, "success");
                await loadRequests();

                setTimeout(() => {
                    const updatedRow = document.querySelector(`tr[data-request-id="${requestId}"]`);
                    if (updatedRow) {
                        updatedRow.style.transition = "background-color 0.4s ease";
                        updatedRow.style.backgroundColor = "rgba(16, 185, 129, 0.25)";
                        setTimeout(() => { updatedRow.style.backgroundColor = ""; }, 1800);
                    }
                }, 120);
            } else if (!resp.ok && (data.requires_override || (data.error && data.error.includes("Budget overcommit")))) {
                if (row) {
                    row.querySelectorAll(".btn-row-action").forEach(b => {
                        b.disabled = false;
                        b.style.opacity = "1";
                    });
                }
                if (btnEl) btnEl.innerHTML = originalHtml;
                const confirmOverride = confirm(
                    `⚠️ Budget Limit Warning:\n\n${data.error}\n\nAuthorize Executive Manager Override to approve this purchase?`
                );
                if (confirmOverride) {
                    return quickApproveRequest(requestId, btnEl, true);
                } else {
                    showToast(`Quick approval cancelled: Budget limit exceeded.`, "warning");
                }
            } else {
                showToast(`Approval failed: ${data.error || "Server error"}`, "danger");
                if (row) {
                    row.querySelectorAll(".btn-row-action").forEach(b => {
                        b.disabled = false;
                        b.style.opacity = "1";
                    });
                }
                if (btnEl) {
                    btnEl.innerHTML = originalHtml;
                }
            }
        } catch (err) {
            console.error("Quick approve error:", err);
            showToast(`Network error: ${err.message}`, "danger");
            if (row) {
                row.querySelectorAll(".btn-row-action").forEach(b => {
                    b.disabled = false;
                    b.style.opacity = "1";
                });
            }
            if (btnEl) {
                btnEl.innerHTML = originalHtml;
            }
        }
    };

    window.quickRejectRequest = async function(requestId, btnEl) {
        if (!requestId) return;
        const originalHtml = btnEl ? btnEl.innerHTML : '<span class="btn-icon">✕</span>';
        const row = btnEl ? btnEl.closest("tr") : document.querySelector(`tr[data-request-id="${requestId}"]`);

        // Disable all quick buttons in this row and show micro loading state
        if (row) {
            row.querySelectorAll(".btn-row-action").forEach(b => {
                b.disabled = true;
                b.style.opacity = "0.5";
            });
        }
        if (btnEl) {
            btnEl.innerHTML = '<span class="btn-spinner-xs"></span>';
        }

        try {
            const resp = await fetch(`/api/procurement/requests/${requestId}/status`, {
                method: "PATCH",
                headers: {
                    "Content-Type": "application/json",
                    "Accept": "application/json"
                },
                body: JSON.stringify({
                    status: "rejected",
                    actor_id: "Purchase Manager",
                    comment: "Rejected via table quick-action."
                })
            });

            const data = await resp.json();

            if (resp.ok && data.success) {
                showToast(`Request ${requestId} rejected.`, "warning");
                await loadRequests();

                setTimeout(() => {
                    const updatedRow = document.querySelector(`tr[data-request-id="${requestId}"]`);
                    if (updatedRow) {
                        updatedRow.style.transition = "background-color 0.4s ease";
                        updatedRow.style.backgroundColor = "rgba(239, 68, 68, 0.25)";
                        setTimeout(() => { updatedRow.style.backgroundColor = ""; }, 1800);
                    }
                }, 120);
            } else {
                showToast(`Rejection failed: ${data.error || "Server error"}`, "danger");
                if (row) {
                    row.querySelectorAll(".btn-row-action").forEach(b => {
                        b.disabled = false;
                        b.style.opacity = "1";
                    });
                }
                if (btnEl) {
                    btnEl.innerHTML = originalHtml;
                }
            }
        } catch (err) {
            console.error("Quick reject error:", err);
            showToast(`Network error: ${err.message}`, "danger");
            if (row) {
                row.querySelectorAll(".btn-row-action").forEach(b => {
                    b.disabled = false;
                    b.style.opacity = "1";
                });
            }
            if (btnEl) {
                btnEl.innerHTML = originalHtml;
            }
        }
    };

    // --------------------------------------------------------------------------
    // 8. Filters & Search Handlers
    // --------------------------------------------------------------------------
    filterPills.forEach(pill => {
        pill.addEventListener("click", () => {
            filterPills.forEach(p => p.classList.remove("active"));
            pill.classList.add("active");
            currentFilter = pill.getAttribute("data-filter");
            renderTable();
        });
    });

    searchInput.addEventListener("input", renderTable);
    btnRefresh.addEventListener("click", () => {
        showToast("Refreshing purchase requests...", "info");
        loadRequests();
    });

    // Initial Load
    loadRequests();
});

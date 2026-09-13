/**
 * Inventory Management Module JavaScript (inventory.js)
 * High-performance, reactive UI for Multi-Warehouse Inventory Management
 * Handles live REST API calls, multi-factor filtering, real-time modal edits,
 * interactive Stock Movement Audit Trail, and Real-time Asset Valuation Analytics.
 */

function initInventory() {
    if (window.__inventoryJsInitialized) {
        return;
    }
    window.__inventoryJsInitialized = true;

    // State Store
    let inventoryItems = [];
    let historyRecords = [];
    let activeEditingSku = null;
    let activeHistorySku = null;
    let activeTab = "catalog";
    let analyticsCharts = {};

    // DOM Elements - Tab Controls
    const tabCatalogBtn = document.getElementById("tabCatalogBtn");
    const tabAnalyticsBtn = document.getElementById("tabAnalyticsBtn");
    const tabHistoryBtn = document.getElementById("tabHistoryBtn");
    const catalogView = document.getElementById("inventoryCatalogView");
    const analyticsView = document.getElementById("inventoryAnalyticsView");
    const historyView = document.getElementById("inventoryHistoryView");

    // DOM Elements - Catalog Controls & Search
    const searchInput = document.getElementById("inventorySearchInput");
    const clearSearchBtn = document.getElementById("clearSearchBtn");
    const categoryFilter = document.getElementById("categoryFilter");
    const statusFilter = document.getElementById("statusFilter");
    const refreshBtn = document.getElementById("refreshInventoryBtn");
    const resetFiltersBtn = document.getElementById("resetFiltersBtn");
    const tableBody = document.getElementById("inventoryTableBody");
    const emptyState = document.getElementById("inventoryEmptyState");
    const countBadge = document.getElementById("tableFilteredCount");

    // DOM Elements - Catalog KPIs
    const kpiTotalItems = document.getElementById("kpiTotalItems");
    const kpiInStock = document.getElementById("kpiInStock");
    const kpiLowStock = document.getElementById("kpiLowStock");
    const kpiOutOfStock = document.getElementById("kpiOutOfStock");
    const kpiTotalUnits = document.getElementById("kpiTotalUnits");

    // DOM Elements - Analytics View
    const anTotalValuation = document.getElementById("anTotalValuation");
    const anTotalUnits = document.getElementById("anTotalUnits");
    const anAvgUnitCost = document.getElementById("anAvgUnitCost");
    const anHealthRatio = document.getElementById("anHealthRatio");
    const anHealthSubtext = document.getElementById("anHealthSubtext");
    const anWarehouseList = document.getElementById("anWarehouseList");
    const anCategoryList = document.getElementById("anCategoryList");
    const anTopAssetsBody = document.getElementById("anTopAssetsBody");
    const anCriticalReorderBody = document.getElementById("anCriticalReorderBody");

    // DOM Elements - History Audit View
    const historySearchInput = document.getElementById("historySearchInput");
    const historyTypeFilter = document.getElementById("historyTypeFilter");
    const refreshHistoryBtn = document.getElementById("refreshHistoryBtn");
    const historyTableBody = document.getElementById("historyTableBody");
    const historyTableCount = document.getElementById("historyTableCount");

    // DOM Elements - Add Item Modal
    const openAddModalBtn = document.getElementById("openAddItemBtn");
    const addItemModal = document.getElementById("addItemModal");
    const closeAddModalBtn = document.getElementById("closeAddModalBtn");
    const cancelAddBtn = document.getElementById("cancelAddBtn");
    const addItemForm = document.getElementById("addItemForm");
    const submitAddBtn = document.getElementById("submitAddItemBtn");
    const addTotalStockPreview = document.getElementById("addTotalStockPreview");

    // DOM Elements - Edit Stock Modal
    const editStockModal = document.getElementById("editStockModal");
    const closeEditModalBtn = document.getElementById("closeEditModalBtn");
    const cancelEditBtn = document.getElementById("cancelEditBtn");
    const editStockForm = document.getElementById("editStockForm");
    const saveStockEditBtn = document.getElementById("saveStockEditBtn");
    const editWarehousesContainer = document.getElementById("editWarehousesContainer");
    const editTotalStockPreview = document.getElementById("editTotalStockPreview");
    const toggleAddWarehouseRowBtn = document.getElementById("toggleAddWarehouseRowBtn");
    const newWarehouseRow = document.getElementById("newWarehouseRow");
    const confirmAddNewWhBtn = document.getElementById("confirmAddNewWhBtn");

    // DOM Elements - SKU History Modal
    const skuHistoryModal = document.getElementById("skuHistoryModal");
    const closeSkuHistoryModalBtn = document.getElementById("closeSkuHistoryModalBtn");
    const skuHistorySkuBadge = document.getElementById("skuHistorySkuBadge");
    const skuHistoryItemName = document.getElementById("skuHistoryItemName");
    const skuHistoryCurrentStock = document.getElementById("skuHistoryCurrentStock");
    const skuTimelineContainer = document.getElementById("skuTimelineContainer");

    // DOM Elements - Toast & Alerts
    const alertBanner = document.getElementById("inventoryAlertBanner");
    const alertText = document.getElementById("inventoryAlertText");
    const alertIcon = document.getElementById("inventoryAlertIcon");
    const toastElem = document.getElementById("inventoryToast");
    const toastMsg = document.getElementById("toastMsg");
    const toastIcon = document.getElementById("toastIcon");

    // =========================================================================
    // 1. Tab Navigation
    // =========================================================================

    function switchInventoryTab(tabName) {
        activeTab = tabName;
        const tabs = [
            { name: "catalog", btn: tabCatalogBtn, view: catalogView },
            { name: "analytics", btn: tabAnalyticsBtn, view: analyticsView },
            { name: "history", btn: tabHistoryBtn, view: historyView }
        ];

        tabs.forEach(t => {
            if (!t.btn || !t.view) return;
            if (t.name === tabName) {
                t.btn.classList.add("active");
                t.view.style.display = "block";
                t.view.classList.add("active");
            } else {
                t.btn.classList.remove("active");
                t.view.style.display = "none";
                t.view.classList.remove("active");
            }
        });

        try {
            const newUrl = tabName === "catalog" ? "/inventory" : (tabName === "analytics" ? "/analytics" : "/history");
            if (window.location.pathname !== newUrl) {
                window.history.replaceState({ tab: tabName }, "", newUrl);
            }
        } catch (e) {}

        if (tabName === "analytics") {
            fetchAnalytics();
        } else if (tabName === "history") {
            fetchHistory();
        }
    }

    if (tabCatalogBtn) tabCatalogBtn.addEventListener("click", () => switchInventoryTab("catalog"));
    if (tabAnalyticsBtn) tabAnalyticsBtn.addEventListener("click", () => switchInventoryTab("analytics"));
    if (tabHistoryBtn) tabHistoryBtn.addEventListener("click", () => switchInventoryTab("history"));

    // =========================================================================
    // 2. Catalog Data Fetching & Sync
    // =========================================================================

    async function fetchInventory(silent = false) {
        if (!silent && tableBody) {
            tableBody.innerHTML = `
                <tr class="loading-placeholder-row">
                    <td colspan="7" class="text-center py-5">
                        <div class="spinner-container">
                            <div class="loading-spinner"></div>
                            <p class="mt-2 text-muted">Retrieving inventory from Google Cloud Firestore...</p>
                        </div>
                    </td>
                </tr>
            `;
            if (emptyState) emptyState.style.display = "none";
        }

        try {
            const res = await fetch("/api/inventory?limit=500");
            const payload = await res.json();

            if (!res.ok || !payload.success) {
                throw new Error(payload.error || "Failed to load inventory.");
            }

            inventoryItems = payload.data || [];
            updateKpiMetrics(inventoryItems);
            applyFiltersAndRender();
        } catch (err) {
            console.error("Error fetching inventory:", err);
            showAlert(`Unable to fetch inventory: ${err.message}`, "error");
            if (tableBody) {
                tableBody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center py-5 text-danger">
                            <p>⚠️ Error loading inventory from Firestore: ${escapeHtml(err.message)}</p>
                            <button class="btn btn-outline btn-sm mt-3" onclick="location.reload()">Retry Connection</button>
                        </td>
                    </tr>
                `;
            }
        }
    }

    // =========================================================================
    // 3. KPI Metrics Computation
    // =========================================================================

    function updateKpiMetrics(items) {
        let totalItems = items.length;
        let inStockCount = 0;
        let lowStockCount = 0;
        let outOfStockCount = 0;
        let totalUnits = 0;

        items.forEach(item => {
            const stock = parseInt(item.total_stock ?? 0, 10);
            const threshold = parseInt(item.reorder_threshold ?? 10, 10);
            totalUnits += stock;

            if (stock === 0) {
                outOfStockCount++;
            } else if (stock <= threshold) {
                lowStockCount++;
            } else {
                inStockCount++;
            }
        });

        if (kpiTotalItems) kpiTotalItems.textContent = totalItems.toLocaleString();
        if (kpiInStock) kpiInStock.textContent = inStockCount.toLocaleString();
        if (kpiLowStock) kpiLowStock.textContent = lowStockCount.toLocaleString();
        if (kpiOutOfStock) kpiOutOfStock.textContent = outOfStockCount.toLocaleString();
        if (kpiTotalUnits) kpiTotalUnits.textContent = totalUnits.toLocaleString();
    }

    // =========================================================================
    // 4. Search, Filtering, and Table Rendering
    // =========================================================================

    function getItemStatus(item) {
        const stock = parseInt(item.total_stock ?? 0, 10);
        const threshold = parseInt(item.reorder_threshold ?? 10, 10);
        if (stock === 0) return "out_of_stock";
        if (stock <= threshold) return "low_stock";
        return "in_stock";
    }

    function applyFiltersAndRender() {
        const query = (searchInput ? searchInput.value : "").trim().toLowerCase();
        const selectedCategory = categoryFilter ? categoryFilter.value : "";
        const selectedStatus = statusFilter ? statusFilter.value : "";

        if (clearSearchBtn) {
            clearSearchBtn.style.display = query.length > 0 ? "block" : "none";
        }

        const filtered = inventoryItems.filter(item => {
            if (query) {
                const skuMatch = (item.sku || "").toLowerCase().includes(query);
                const nameMatch = (item.name || "").toLowerCase().includes(query);
                const catMatch = (item.category || "").toLowerCase().includes(query);
                if (!skuMatch && !nameMatch && !catMatch) return false;
            }

            if (selectedCategory && item.category !== selectedCategory) {
                return false;
            }

            if (selectedStatus) {
                const status = getItemStatus(item);
                if (status !== selectedStatus) return false;
            }

            return true;
        });

        renderTable(filtered);
    }

    function renderTable(items) {
        if (!tableBody) return;

        if (countBadge) {
            countBadge.textContent = `Showing ${items.length} of ${inventoryItems.length} products`;
        }

        if (items.length === 0) {
            tableBody.innerHTML = "";
            if (emptyState) emptyState.style.display = "block";
            return;
        }

        if (emptyState) emptyState.style.display = "none";

        const html = items.map(item => {
            const status = getItemStatus(item);
            let statusBadge = "";
            if (status === "in_stock") {
                statusBadge = `<span class="badge-stock badge-in-stock">🟢 In Stock</span>`;
            } else if (status === "low_stock") {
                statusBadge = `<span class="badge-stock badge-low-stock">🟡 Low Stock (&le; ${item.reorder_threshold ?? 10})</span>`;
            } else {
                statusBadge = `<span class="badge-stock badge-out-stock">🔴 Out of Stock</span>`;
            }

            const warehouses = item.warehouses || {};
            const whKeys = Object.keys(warehouses);
            let whChipsHtml = "";

            if (whKeys.length === 0) {
                whChipsHtml = `<span class="text-muted text-sm">No regional depots assigned</span>`;
            } else {
                whChipsHtml = whKeys.map(k => {
                    const wh = warehouses[k];
                    const whStock = typeof wh === "object" ? (wh.stock ?? 0) : wh;
                    const stockClass = whStock === 0 ? "chip-zero" : (whStock <= 5 ? "chip-warn" : "chip-healthy");
                    const locTitle = typeof wh === "object" ? (wh.location_name || k) : k;
                    return `<span class="wh-stock-chip ${stockClass}" title="${escapeHtml(locTitle)}: ${whStock} units">
                        <strong>${escapeHtml(k)}:</strong> ${whStock}
                    </span>`;
                }).join(" ");
            }

            const unitCostDisplay = item.unit_cost 
                ? `$${parseFloat(item.unit_cost).toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}` 
                : "-";

            return `
                <tr class="inventory-row" data-sku="${escapeHtml(item.sku)}">
                    <td>
                        <div class="item-title-cell">
                            <span class="item-icon-box">📦</span>
                            <div>
                                <strong class="item-name-text">${escapeHtml(item.name || item.sku)}</strong>
                                <span class="item-cost-subtext">Est. Cost: ${unitCostDisplay}</span>
                            </div>
                        </div>
                    </td>
                    <td>
                        <span class="font-mono sku-code-badge">${escapeHtml(item.sku)}</span>
                    </td>
                    <td>
                        <span class="category-pill">${escapeHtml(item.category || "General")}</span>
                    </td>
                    <td>
                        <div class="warehouse-chips-wrap">
                            ${whChipsHtml}
                        </div>
                    </td>
                    <td class="text-center font-bold total-stock-cell">
                        <span class="stock-total-number ${status === 'out_of_stock' ? 'text-danger' : (status === 'low_stock' ? 'text-warning' : 'text-primary')}">
                            ${parseInt(item.total_stock ?? 0, 10).toLocaleString()}
                        </span>
                    </td>
                    <td class="text-center">
                        ${statusBadge}
                    </td>
                    <td class="text-right" style="white-space: nowrap;">
                        <button class="btn btn-sm btn-outline btn-sku-history" data-sku="${escapeHtml(item.sku)}" title="Stock Movement Timeline" style="margin-right: 6px;">
                            📜 History
                        </button>
                        <button class="btn btn-sm btn-outline btn-edit-stock" data-sku="${escapeHtml(item.sku)}" title="Adjust warehouse stock">
                            ✏️ Edit Stock
                        </button>
                    </td>
                </tr>
            `;
        }).join("");

        tableBody.innerHTML = html;

        // Attach event listeners to Edit Stock and SKU History buttons
        tableBody.querySelectorAll(".btn-edit-stock").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const sku = e.currentTarget.getAttribute("data-sku");
                openEditStockModal(sku);
            });
        });

        tableBody.querySelectorAll(".btn-sku-history").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const sku = e.currentTarget.getAttribute("data-sku");
                openSkuHistoryModal(sku);
            });
        });
    }

    // =========================================================================
    // 5. Add New Item Modal & Handler
    // =========================================================================

    function calculateAddTotalPreview() {
        if (!addTotalStockPreview || !addItemModal) return;
        const inputs = addItemModal.querySelectorAll(".add-wh-calc");
        let total = 0;
        inputs.forEach(inp => {
            total += Math.max(0, parseInt(inp.value || 0, 10));
        });
        addTotalStockPreview.textContent = `${total.toLocaleString()} Units`;
    }

    function openAddModal() {
        if (!addItemModal) return;
        if (addItemForm) addItemForm.reset();
        const costInp = document.getElementById("addUnitCost");
        const threshInp = document.getElementById("addReorderThreshold");
        const nInp = document.getElementById("addWhNorthStock");
        const wInp = document.getElementById("addWhWestStock");
        const eInp = document.getElementById("addWhEastStock");
        const sInp = document.getElementById("addWhSouthStock");

        if (costInp) costInp.value = "0.00";
        if (threshInp) threshInp.value = "10";
        if (nInp) nInp.value = "0";
        if (wInp) wInp.value = "0";
        if (eInp) eInp.value = "0";
        if (sInp) sInp.value = "0";
        calculateAddTotalPreview();

        addItemModal.style.display = "flex";
        setTimeout(() => {
            const skuInput = document.getElementById("addSku");
            if (skuInput) skuInput.focus();
        }, 50);
    }

    function closeAddModal() {
        if (addItemModal) addItemModal.style.display = "none";
    }

    if (openAddModalBtn) openAddModalBtn.addEventListener("click", openAddModal);
    if (closeAddModalBtn) closeAddModalBtn.addEventListener("click", closeAddModal);
    if (cancelAddBtn) cancelAddBtn.addEventListener("click", closeAddModal);

    if (addItemModal) {
        addItemModal.querySelectorAll(".add-wh-calc").forEach(inp => {
            inp.addEventListener("input", calculateAddTotalPreview);
        });
    }

    if (addItemForm) {
        addItemForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const sku = (document.getElementById("addSku")?.value || "").trim().toUpperCase();
            const name = (document.getElementById("addName")?.value || "").trim();
            const category = (document.getElementById("addCategory")?.value || "").trim();
            const unitCost = parseFloat(document.getElementById("addUnitCost")?.value || 0);
            const reorderThreshold = parseInt(document.getElementById("addReorderThreshold")?.value || 10, 10);

            const whNorthStock = Math.max(0, parseInt(document.getElementById("addWhNorthStock")?.value || 0, 10));
            const whWestStock = Math.max(0, parseInt(document.getElementById("addWhWestStock")?.value || 0, 10));
            const whEastStock = Math.max(0, parseInt(document.getElementById("addWhEastStock")?.value || 0, 10));
            const whSouthStock = Math.max(0, parseInt(document.getElementById("addWhSouthStock")?.value || 0, 10));

            if (!sku || !name || !category) {
                showAlert("Please provide SKU, Product Name, and Category.", "warning");
                return;
            }

            const payload = {
                sku: sku,
                name: name,
                category: category,
                unit_cost: unitCost,
                reorder_threshold: reorderThreshold,
                warehouses: {
                    "WH-NORTH": { location_name: "Chicago Hub", stock: whNorthStock, bin_shelf: "A-01-1" },
                    "WH-WEST":  { location_name: "Seattle Hub", stock: whWestStock, bin_shelf: "W-01-1" },
                    "WH-EAST":  { location_name: "New York Hub", stock: whEastStock, bin_shelf: "E-01-1" },
                    "WH-SOUTH": { location_name: "Austin Hub", stock: whSouthStock, bin_shelf: "S-01-1" }
                }
            };

            setButtonLoading(submitAddBtn, true, "Saving...");

            try {
                const res = await fetch("/api/inventory", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();

                if (!res.ok || !data.success) {
                    throw new Error(data.error || "Failed to create inventory item.");
                }

                closeAddModal();
                showToast(`Item '${sku}' registered successfully!`, "success");
                showAlert(`Inventory Item '${sku}' (${name}) was successfully added to Firestore.`, "success");
                
                // Refresh catalog and analytics
                await fetchInventory(true);
            } catch (err) {
                console.error("Error creating item:", err);
                showAlert(err.message, "error");
            } finally {
                setButtonLoading(submitAddBtn, false, "Create Inventory Item");
            }
        });
    }

    // =========================================================================
    // 6. Edit Stock Modal & Handlers
    // =========================================================================

    function calculateEditTotalPreview() {
        if (!editWarehousesContainer || !editTotalStockPreview) return;
        const inputs = editWarehousesContainer.querySelectorAll(".edit-wh-stock-input");
        let total = 0;
        inputs.forEach(inp => {
            total += Math.max(0, parseInt(inp.value || 0, 10));
        });
        editTotalStockPreview.textContent = `${total.toLocaleString()} Units`;
    }

    function openEditStockModal(sku) {
        const item = inventoryItems.find(i => i.sku === sku);
        if (!item) {
            showAlert(`Item with SKU '${sku}' not found in current view.`, "warning");
            return;
        }

        activeEditingSku = sku;

        const skuBadge = document.getElementById("editModalSkuBadge");
        const itemName = document.getElementById("editModalItemName");
        const itemMeta = document.getElementById("editModalItemMeta");
        const curStock = document.getElementById("editModalCurrentStock");

        if (skuBadge) skuBadge.textContent = item.sku;
        if (itemName) itemName.textContent = item.name || item.sku;
        const costStr = item.unit_cost ? `$${parseFloat(item.unit_cost).toFixed(2)}` : "N/A";
        if (itemMeta) itemMeta.textContent = `${item.category || "General"} | Unit Cost: ${costStr}`;
        if (curStock) curStock.textContent = `${(item.total_stock ?? 0).toLocaleString()} Units`;

        const threshInp = document.getElementById("editReorderThreshold");
        const costInp = document.getElementById("editUnitCost");
        if (threshInp) threshInp.value = item.reorder_threshold ?? 10;
        if (costInp) costInp.value = item.unit_cost ?? 0.00;

        if (newWarehouseRow) newWarehouseRow.style.display = "none";
        const newCode = document.getElementById("newWhCode");
        const newLoc = document.getElementById("newWhLocation");
        const newStk = document.getElementById("newWhStock");
        if (newCode) newCode.value = "";
        if (newLoc) newLoc.value = "";
        if (newStk) newStk.value = "0";

        renderEditWarehousesList(item.warehouses || {});
        calculateEditTotalPreview();

        if (editStockModal) editStockModal.style.display = "flex";
    }

    function renderEditWarehousesList(warehouses) {
        if (!editWarehousesContainer) return;
        const whKeys = Object.keys(warehouses);
        if (whKeys.length === 0) {
            editWarehousesContainer.innerHTML = `<p class="text-muted text-sm">No warehouses configured for this item. Add one below.</p>`;
            return;
        }

        const html = whKeys.map(k => {
            const wh = warehouses[k];
            const stock = typeof wh === "object" ? (wh.stock ?? 0) : wh;
            const locationName = typeof wh === "object" ? (wh.location_name || k) : k;
            const binShelf = typeof wh === "object" ? (wh.bin_shelf || "A-01") : "A-01";

            return `
                <div class="edit-wh-row" data-wh-code="${escapeHtml(k)}">
                    <div class="wh-meta-cell">
                        <span class="wh-code-pill">${escapeHtml(k)}</span>
                        <div class="wh-loc-texts">
                            <strong class="wh-loc-name">${escapeHtml(locationName)}</strong>
                            <span class="wh-bin-text">Bin/Shelf: ${escapeHtml(binShelf)}</span>
                        </div>
                    </div>
                    <div class="wh-stepper-cell">
                        <div class="stepper-controls">
                            <button type="button" class="btn-step btn-step-sub10" data-delta="-10">-10</button>
                            <button type="button" class="btn-step btn-step-sub1" data-delta="-1">-1</button>
                            <input 
                                type="number" 
                                class="form-control edit-wh-stock-input font-mono" 
                                data-wh-code="${escapeHtml(k)}" 
                                data-wh-loc="${escapeHtml(locationName)}"
                                data-wh-bin="${escapeHtml(binShelf)}"
                                value="${stock}" 
                                min="0"
                            >
                            <button type="button" class="btn-step btn-step-add1" data-delta="1">+1</button>
                            <button type="button" class="btn-step btn-step-add10" data-delta="10">+10</button>
                        </div>
                    </div>
                </div>
            `;
        }).join("");

        editWarehousesContainer.innerHTML = html;

        editWarehousesContainer.querySelectorAll(".btn-step").forEach(btn => {
            btn.addEventListener("click", (e) => {
                const delta = parseInt(e.currentTarget.getAttribute("data-delta"), 10);
                const row = e.currentTarget.closest(".edit-wh-row");
                const input = row.querySelector(".edit-wh-stock-input");
                let cur = parseInt(input.value || 0, 10);
                let next = Math.max(0, cur + delta);
                input.value = next;
                calculateEditTotalPreview();
            });
        });

        editWarehousesContainer.querySelectorAll(".edit-wh-stock-input").forEach(inp => {
            inp.addEventListener("input", calculateEditTotalPreview);
        });
    }

    function closeEditModal() {
        if (editStockModal) editStockModal.style.display = "none";
        activeEditingSku = null;
    }

    if (closeEditModalBtn) closeEditModalBtn.addEventListener("click", closeEditModal);
    if (cancelEditBtn) cancelEditBtn.addEventListener("click", closeEditModal);

    if (toggleAddWarehouseRowBtn && newWarehouseRow) {
        toggleAddWarehouseRowBtn.addEventListener("click", () => {
            const isHidden = newWarehouseRow.style.display === "none";
            newWarehouseRow.style.display = isHidden ? "flex" : "none";
            if (isHidden) {
                const codeInp = document.getElementById("newWhCode");
                if (codeInp) codeInp.focus();
            }
        });
    }

    if (confirmAddNewWhBtn) {
        confirmAddNewWhBtn.addEventListener("click", () => {
            const code = (document.getElementById("newWhCode")?.value || "").trim().toUpperCase();
            const loc = (document.getElementById("newWhLocation")?.value || "").trim() || code;
            const stock = Math.max(0, parseInt(document.getElementById("newWhStock")?.value || 0, 10));

            if (!code) {
                alert("Please enter a Warehouse Code (e.g. WH-SOUTH).");
                return;
            }

            const existingInput = editWarehousesContainer.querySelector(`[data-wh-code="${code}"]`);
            if (existingInput) {
                alert(`Warehouse '${code}' is already present. Adjust its stock directly.`);
                return;
            }

            const newRow = document.createElement("div");
            newRow.className = "edit-wh-row";
            newRow.setAttribute("data-wh-code", code);
            newRow.innerHTML = `
                <div class="wh-meta-cell">
                    <span class="wh-code-pill">${escapeHtml(code)}</span>
                    <div class="wh-loc-texts">
                        <strong class="wh-loc-name">${escapeHtml(loc)}</strong>
                        <span class="wh-bin-text">Bin/Shelf: NEW</span>
                    </div>
                </div>
                <div class="wh-stepper-cell">
                    <div class="stepper-controls">
                        <button type="button" class="btn-step btn-step-sub10" data-delta="-10">-10</button>
                        <button type="button" class="btn-step btn-step-sub1" data-delta="-1">-1</button>
                        <input 
                            type="number" 
                            class="form-control edit-wh-stock-input font-mono" 
                            data-wh-code="${escapeHtml(code)}" 
                            data-wh-loc="${escapeHtml(loc)}"
                            data-wh-bin="NEW"
                            value="${stock}" 
                            min="0"
                        >
                        <button type="button" class="btn-step btn-step-add1" data-delta="1">+1</button>
                        <button type="button" class="btn-step btn-step-add10" data-delta="10">+10</button>
                    </div>
                </div>
            `;
            editWarehousesContainer.appendChild(newRow);

            newRow.querySelectorAll(".btn-step").forEach(btn => {
                btn.addEventListener("click", (e) => {
                    const delta = parseInt(e.currentTarget.getAttribute("data-delta"), 10);
                    const input = newRow.querySelector(".edit-wh-stock-input");
                    let cur = parseInt(input.value || 0, 10);
                    let next = Math.max(0, cur + delta);
                    input.value = next;
                    calculateEditTotalPreview();
                });
            });
            newRow.querySelector(".edit-wh-stock-input").addEventListener("input", calculateEditTotalPreview);

            document.getElementById("newWhCode").value = "";
            document.getElementById("newWhLocation").value = "";
            document.getElementById("newWhStock").value = "0";
            newWarehouseRow.style.display = "none";
            calculateEditTotalPreview();
        });
    }

    if (editStockForm) {
        editStockForm.addEventListener("submit", async (e) => {
            e.preventDefault();
            if (!activeEditingSku) return;

            const inputs = editWarehousesContainer.querySelectorAll(".edit-wh-stock-input");
            const updatedWarehouses = {};

            inputs.forEach(inp => {
                const code = inp.getAttribute("data-wh-code");
                const loc = inp.getAttribute("data-wh-loc") || code;
                const bin = inp.getAttribute("data-wh-bin") || "A-01";
                const stock = Math.max(0, parseInt(inp.value || 0, 10));

                updatedWarehouses[code] = {
                    location_name: loc,
                    stock: stock,
                    bin_shelf: bin
                };
            });

            const reorderThreshold = parseInt(document.getElementById("editReorderThreshold")?.value || 10, 10);
            const unitCost = parseFloat(document.getElementById("editUnitCost")?.value || 0);

            const payload = {
                warehouses: updatedWarehouses,
                reorder_threshold: reorderThreshold,
                unit_cost: unitCost
            };

            setButtonLoading(saveStockEditBtn, true, "Updating...");

            try {
                const res = await fetch(`/api/inventory/${encodeURIComponent(activeEditingSku)}`, {
                    method: "PUT",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify(payload)
                });

                const data = await res.json();

                if (!res.ok || !data.success) {
                    throw new Error(data.error || "Failed to update inventory.");
                }

                closeEditModal();
                showToast(`Stock updated for '${activeEditingSku}'!`, "success");
                showAlert(`SKU '${activeEditingSku}' stock adjusted in Firestore. New total: ${data.data.total_stock} units.`, "success");

                // Refresh catalog automatically
                await fetchInventory(true);
            } catch (err) {
                console.error("Error updating stock:", err);
                showAlert(err.message, "error");
            } finally {
                setButtonLoading(saveStockEditBtn, false, "Update Stock Levels");
            }
        });
    }

    // =========================================================================
    // 7. Inventory Analytics View Logic
    // =========================================================================

    async function fetchAnalytics() {
        if (!anTotalValuation) return;
        try {
            anTotalValuation.textContent = "Calculating...";
            const res = await fetch("/api/inventory/analytics");
            const payload = await res.json();

            if (!res.ok || !payload.success) {
                throw new Error(payload.error || "Failed to load inventory analytics.");
            }

            renderAnalytics(payload.data);
        } catch (err) {
            console.error("Error loading analytics:", err);
            showAlert(`Unable to load analytics: ${err.message}`, "error");
            if (anTotalValuation) anTotalValuation.textContent = "Error";
        }
    }

    function renderAnalytics(data) {
        if (!data) return;
        const summary = data.summary || {};
        const warehouses = data.warehouses || [];
        const categories = data.categories || [];
        const topAssets = data.top_assets || [];
        const criticalReorders = data.critical_reorders || [];

        // Header Metrics
        if (anTotalValuation) {
            anTotalValuation.textContent = `$${(summary.total_asset_value || 0).toLocaleString(undefined, {
                minimumFractionDigits: 2, 
                maximumFractionDigits: 2
            })}`;
        }
        if (anTotalUnits) {
            anTotalUnits.textContent = `${(summary.total_units || 0).toLocaleString()} Units`;
        }
        if (anAvgUnitCost) {
            anAvgUnitCost.textContent = `$${(summary.average_unit_cost || 0).toFixed(2)}`;
        }
        if (anHealthRatio) {
            anHealthRatio.textContent = `${(summary.health_ratio_pct || 0).toFixed(1)}%`;
        }
        if (anHealthSubtext) {
            anHealthSubtext.textContent = `${summary.healthy_count || 0} healthy, ${summary.low_stock_count || 0} low, ${summary.out_of_stock_count || 0} empty (${summary.total_skus || 0} total SKUs)`;
        }

        // Warehouse Regional Breakdown
        if (anWarehouseList) {
            if (warehouses.length === 0) {
                anWarehouseList.innerHTML = `<p class="text-muted text-center py-4">No regional hubs registered.</p>`;
            } else {
                const whColors = ["#3b82f6", "#10b981", "#8b5cf6", "#f59e0b", "#ec4899", "#06b6d4"];
                anWarehouseList.innerHTML = warehouses.map((wh, idx) => {
                    const color = whColors[idx % whColors.length];
                    return `
                        <div class="warehouse-dist-item">
                            <div class="dist-header-meta">
                                <span class="dist-name">
                                    <span class="wh-code-pill" style="font-size: 0.72rem;">${escapeHtml(wh.hub_code)}</span>
                                    <span>${escapeHtml(wh.name)}</span>
                                </span>
                                <span class="dist-values">
                                    <strong>${wh.units.toLocaleString()} units</strong> 
                                    (${wh.percentage.toFixed(1)}%) &bull; 
                                    $${wh.asset_value.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}
                                </span>
                            </div>
                            <div class="dist-progress-bar">
                                <div class="dist-progress-fill" style="width: ${Math.min(100, Math.max(2, wh.percentage))}%; background: ${color};"></div>
                            </div>
                        </div>
                    `;
                }).join("");
            }
        }

        // Category Capital Breakdown
        if (anCategoryList) {
            if (categories.length === 0) {
                anCategoryList.innerHTML = `<p class="text-muted text-center py-4">No categories found in catalog.</p>`;
            } else {
                const catColors = ["#6366f1", "#14b8a6", "#f97316", "#a855f7", "#3b82f6", "#ef4444"];
                anCategoryList.innerHTML = categories.map((cat, idx) => {
                    const color = catColors[idx % catColors.length];
                    return `
                        <div class="category-breakdown-item">
                            <div class="dist-header-meta">
                                <span class="dist-name">
                                    <span class="category-pill" style="font-size: 0.72rem;">${escapeHtml(cat.category)}</span>
                                    <span class="text-muted" style="font-size: 0.76rem;">${cat.sku_count} SKUs</span>
                                </span>
                                <span class="dist-values">
                                    <strong>$${cat.asset_value.toLocaleString(undefined, {minimumFractionDigits: 0, maximumFractionDigits: 0})}</strong>
                                    (${cat.percentage.toFixed(1)}%) &bull; ${cat.units.toLocaleString()} units
                                </span>
                            </div>
                            <div class="dist-progress-bar">
                                <div class="dist-progress-fill" style="width: ${Math.min(100, Math.max(2, cat.percentage))}%; background: ${color};"></div>
                            </div>
                        </div>
                    `;
                }).join("");
            }
        }

        // Top High-Value Assets
        if (anTopAssetsBody) {
            if (topAssets.length === 0) {
                anTopAssetsBody.innerHTML = `<tr><td colspan="5" class="text-center text-muted py-3">No inventory items available.</td></tr>`;
            } else {
                anTopAssetsBody.innerHTML = topAssets.map(item => {
                    const st = Number(item.stock ?? item.total_stock ?? 0);
                    const uc = Number(item.unit_cost ?? 0);
                    const av = Number(item.asset_value ?? 0);
                    return `
                    <tr>
                        <td><strong>${escapeHtml(item.name || item.sku)}</strong></td>
                        <td><span class="font-mono text-xs">${escapeHtml(item.sku)}</span></td>
                        <td>${st.toLocaleString()}</td>
                        <td>$${uc.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                        <td style="text-align: right; font-weight: 700; color: var(--success);">$${av.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}</td>
                    </tr>
                `;}).join("");
            }
        }

        // Critical Reorder Radar
        if (anCriticalReorderBody) {
            if (criticalReorders.length === 0) {
                anCriticalReorderBody.innerHTML = `
                    <tr>
                        <td colspan="5" class="text-center text-success py-4">
                            ✅ <strong>All items meet safety reorder thresholds!</strong> No replenishment deficits.
                        </td>
                    </tr>
                `;
            } else {
                anCriticalReorderBody.innerHTML = criticalReorders.map(item => {
                    const st = Number(item.stock ?? item.current_stock ?? 0);
                    const rt = Number(item.reorder_threshold ?? 10);
                    const def = Number(item.deficit ?? 0);
                    const rc = Number(item.restock_cost ?? item.estimated_restock_cost ?? 0);
                    return `
                    <tr>
                        <td><strong>${escapeHtml(item.name || item.sku)}</strong></td>
                        <td><span class="font-mono text-xs">${escapeHtml(item.sku)}</span></td>
                        <td>
                            <span class="${st === 0 ? 'text-danger' : 'text-warning'} font-bold">
                                ${st} / min ${rt}
                            </span>
                        </td>
                        <td><span class="change-pill-neg">-${def}</span></td>
                        <td style="text-align: right; font-weight: 700; color: #fbbf24;">
                            $${rc.toLocaleString(undefined, {minimumFractionDigits: 2, maximumFractionDigits: 2})}
                        </td>
                    </tr>
                `;}).join("");
            }
        }

        // Render Live Interactive Chart.js Graphs
        renderAnalyticsCharts(data);
    }

    function renderAnalyticsCharts(data) {
        if (!window.Chart) {
            console.warn("Chart.js is not loaded yet. Retrying in 250ms...");
            setTimeout(() => {
                if (window.Chart) renderAnalyticsCharts(data);
            }, 250);
            return;
        }

        // Set global dark theme defaults for Chart.js
        Chart.defaults.color = "#94a3b8";
        Chart.defaults.font.family = "'Plus Jakarta Sans', sans-serif";
        Chart.defaults.borderColor = "rgba(255, 255, 255, 0.08)";

        const summary = data.summary || {};
        const warehouses = data.warehouses || [];
        const categories = data.categories || [];
        const topAssets = data.top_assets || [];

        // 1. Chart: Regional Hubs (Bar Chart)
        try {
            const ctxWh = document.getElementById("chartWarehouseHubs");
            if (ctxWh) {
                if (analyticsCharts.warehouse) {
                    analyticsCharts.warehouse.destroy();
                }

                const whLabels = warehouses.map(w => w.name || w.hub_code);
                const whValuations = warehouses.map(w => Number(w.asset_value || w.valuation || 0));
                const whUnits = warehouses.map(w => Number(w.units || 0));

                analyticsCharts.warehouse = new Chart(ctxWh, {
                    type: "bar",
                    data: {
                        labels: whLabels,
                        datasets: [
                            {
                                label: "Asset Valuation ($)",
                                data: whValuations,
                                backgroundColor: "rgba(99, 102, 241, 0.75)",
                                borderColor: "#6366f1",
                                borderWidth: 1.5,
                                borderRadius: 6,
                                yAxisID: "yVal",
                            },
                            {
                                label: "Physical Units",
                                data: whUnits,
                                backgroundColor: "rgba(14, 165, 233, 0.7)",
                                borderColor: "#0ea5e9",
                                borderWidth: 1.5,
                                borderRadius: 6,
                                yAxisID: "yUnits",
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        interaction: {
                            mode: "index",
                            intersect: false,
                        },
                        plugins: {
                            legend: {
                                position: "top",
                                labels: { boxWidth: 12, padding: 12, font: { size: 11 } }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        if (context.dataset.yAxisID === "yVal") {
                                            return ` Valuation: $${Number(context.raw || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                                        }
                                        return ` Physical Stock: ${Number(context.raw || 0).toLocaleString()} Units`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                grid: { display: false }
                            },
                            yVal: {
                                type: "linear",
                                position: "left",
                                ticks: {
                                    callback: function(val) {
                                        return "$" + (val >= 1000 ? (val / 1000).toFixed(0) + "k" : val);
                                    }
                                },
                                grid: { color: "rgba(255, 255, 255, 0.05)" }
                            },
                            yUnits: {
                                type: "linear",
                                position: "right",
                                grid: { drawOnChartArea: false },
                                ticks: {
                                    callback: function(val) {
                                        return val + "u";
                                    }
                                }
                            }
                        }
                    }
                });
            }
        } catch (err) {
            console.error("Error rendering Regional Hubs chart:", err);
        }

        // 2. Chart: Category Capital Share (Doughnut Chart)
        try {
            const ctxCat = document.getElementById("chartCategoryShare");
            if (ctxCat) {
                if (analyticsCharts.category) {
                    analyticsCharts.category.destroy();
                }

                const catLabels = categories.length > 0 ? categories.map(c => c.category || c.name) : ["General"];
                const catValues = categories.length > 0 ? categories.map(c => Number(c.asset_value || c.valuation || 0)) : [0];
                const catColors = [
                    "#6366f1", "#10b981", "#f59e0b", "#ec4899", "#8b5cf6", "#06b6d4", "#3b82f6", "#ef4444"
                ];

                analyticsCharts.category = new Chart(ctxCat, {
                    type: "doughnut",
                    data: {
                        labels: catLabels,
                        datasets: [
                            {
                                data: catValues,
                                backgroundColor: catColors.slice(0, catLabels.length),
                                borderWidth: 2,
                                borderColor: "#161d2f",
                                hoverOffset: 6,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: "64%",
                        plugins: {
                            legend: {
                                position: "right",
                                labels: {
                                    boxWidth: 12,
                                    padding: 12,
                                    font: { size: 11 }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const val = Number(context.raw || 0);
                                        const pct = total > 0 ? ((val / total) * 100).toFixed(1) : "0";
                                        return ` $${val.toLocaleString(undefined, {minimumFractionDigits: 2})} (${pct}%)`;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        } catch (err) {
            console.error("Error rendering Category Share chart:", err);
        }

        // 3. Chart: Top Valued Assets Comparison (Horizontal Bar)
        try {
            const ctxTop = document.getElementById("chartTopAssets");
            if (ctxTop) {
                if (analyticsCharts.topAssets) {
                    analyticsCharts.topAssets.destroy();
                }

                const sliceTop = (topAssets || []).slice(0, 5);
                const topLabels = sliceTop.length > 0 
                    ? sliceTop.map(item => {
                        const name = item.name || item.sku || "Unknown";
                        return name.length > 20 ? name.substring(0, 18) + "..." : name;
                    })
                    : ["No Assets"];
                const topValues = sliceTop.length > 0 
                    ? sliceTop.map(item => Number(item.asset_value || 0))
                    : [0];

                analyticsCharts.topAssets = new Chart(ctxTop, {
                    type: "bar",
                    data: {
                        labels: topLabels,
                        datasets: [
                            {
                                label: "Total Asset Value ($)",
                                data: topValues,
                                backgroundColor: "rgba(16, 185, 129, 0.75)",
                                borderColor: "#10b981",
                                borderWidth: 1.5,
                                borderRadius: 6,
                            }
                        ]
                    },
                    options: {
                        indexAxis: "y",
                        responsive: true,
                        maintainAspectRatio: false,
                        plugins: {
                            legend: { display: false },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        return ` Asset Value: $${Number(context.raw || 0).toLocaleString(undefined, {minimumFractionDigits: 2})}`;
                                    }
                                }
                            }
                        },
                        scales: {
                            x: {
                                ticks: {
                                    callback: function(val) {
                                        return "$" + (val >= 1000 ? (val / 1000).toFixed(0) + "k" : val);
                                    }
                                },
                                grid: { color: "rgba(255, 255, 255, 0.05)" }
                            },
                            y: {
                                grid: { display: false }
                            }
                        }
                    }
                });
            }
        } catch (err) {
            console.error("Error rendering Top Assets chart:", err);
        }

        // 4. Chart: Catalog Stock Health Status (Doughnut)
        try {
            const ctxHealth = document.getElementById("chartStockHealth");
            if (ctxHealth) {
                if (analyticsCharts.health) {
                    analyticsCharts.health.destroy();
                }

                const healthy = Number(summary.healthy_count || 0);
                const lowStock = Number(summary.low_stock_count || 0);
                const outOfStock = Number(summary.out_of_stock_count || 0);

                analyticsCharts.health = new Chart(ctxHealth, {
                    type: "doughnut",
                    data: {
                        labels: ["Healthy In Stock", "Low Stock Warning", "Out of Stock"],
                        datasets: [
                            {
                                data: [healthy, lowStock, outOfStock],
                                backgroundColor: ["#10b981", "#f59e0b", "#ef4444"],
                                borderWidth: 2,
                                borderColor: "#161d2f",
                                hoverOffset: 6,
                            }
                        ]
                    },
                    options: {
                        responsive: true,
                        maintainAspectRatio: false,
                        cutout: "60%",
                        plugins: {
                            legend: {
                                position: "bottom",
                                labels: {
                                    boxWidth: 12,
                                    padding: 10,
                                    font: { size: 11 }
                                }
                            },
                            tooltip: {
                                callbacks: {
                                    label: function(context) {
                                        const count = Number(context.raw || 0);
                                        const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                        const pct = total > 0 ? ((count / total) * 100).toFixed(1) : "0";
                                        return ` ${context.label}: ${count} items (${pct}%)`;
                                    }
                                }
                            }
                        }
                    }
                });
            }
        } catch (err) {
            console.error("Error rendering Stock Health chart:", err);
        }
    }

    // =========================================================================
    // 8. Stock Movement Audit Trail Logic
    // =========================================================================

    async function fetchHistory(silent = false) {
        if (!historyTableBody) return;
        if (!silent) {
            historyTableBody.innerHTML = `
                <tr class="loading-placeholder-row">
                    <td colspan="7" class="text-center py-5">
                        <div class="spinner-container">
                            <div class="loading-spinner"></div>
                            <p class="mt-2 text-muted">Retrieving stock movement audit trail from Firestore...</p>
                        </div>
                    </td>
                </tr>
            `;
        }

        try {
            const res = await fetch("/api/inventory/history?limit=100");
            const payload = await res.json();

            if (!res.ok || !payload.success) {
                throw new Error(payload.error || "Failed to load stock movements.");
            }

            historyRecords = payload.data || [];
            renderHistoryTable();
        } catch (err) {
            console.error("Error loading history:", err);
            showAlert(`Unable to load stock history: ${err.message}`, "error");
            if (historyTableBody) {
                historyTableBody.innerHTML = `
                    <tr>
                        <td colspan="7" class="text-center py-5 text-danger">
                            <p>⚠️ Error loading audit trail: ${escapeHtml(err.message)}</p>
                            <button class="btn btn-outline btn-sm mt-3" onclick="if(window.fetchHistory) window.fetchHistory();">Retry History Fetch</button>
                        </td>
                    </tr>
                `;
            }
        }
    }

    function renderHistoryTable() {
        if (!historyTableBody) return;
        const query = (historySearchInput ? historySearchInput.value : "").trim().toLowerCase();
        const typeFilter = historyTypeFilter ? historyTypeFilter.value : "";

        const filtered = historyRecords.filter(rec => {
            if (typeFilter && rec.movement_type !== typeFilter) return false;
            if (query) {
                const skuMatch = (rec.sku || "").toLowerCase().includes(query);
                const nameMatch = (rec.item_name || "").toLowerCase().includes(query);
                const initMatch = (rec.initiated_by || "").toLowerCase().includes(query);
                const notesMatch = (rec.notes || "").toLowerCase().includes(query);
                const whMatch = (rec.warehouse_code || "").toLowerCase().includes(query);
                if (!skuMatch && !nameMatch && !initMatch && !notesMatch && !whMatch) return false;
            }
            return true;
        });

        if (historyTableCount) {
            historyTableCount.textContent = `Showing ${filtered.length} of ${historyRecords.length} movement records`;
        }

        if (filtered.length === 0) {
            historyTableBody.innerHTML = `
                <tr>
                    <td colspan="7" class="text-center py-5 text-muted">
                        <p style="font-size: 1.1rem; margin-bottom: 0.5rem;">📜 No stock movements found matching filter.</p>
                    </td>
                </tr>
            `;
            return;
        }

        historyTableBody.innerHTML = filtered.map(rec => {
            const delta = parseInt(rec.quantity_delta || 0, 10);
            const deltaHtml = delta >= 0 
                ? `<span class="change-pill-pos">+${delta}</span>` 
                : `<span class="change-pill-neg">${delta}</span>`;

            let typeBadge = "";
            if (rec.movement_type === "auto_allocation") {
                typeBadge = `<span class="movement-type-badge mv-auto-allocation">⚡ AI Allocation</span>`;
            } else if (rec.movement_type === "creation") {
                typeBadge = `<span class="movement-type-badge mv-creation">✨ Initial Stock</span>`;
            } else {
                typeBadge = `<span class="movement-type-badge mv-manual-adjustment">🛠️ Manual Adjust</span>`;
            }

            const dateStr = rec.timestamp 
                ? new Date(rec.timestamp).toISOString().replace("T", " ").substring(0, 19)
                : "Recent";

            return `
                <tr class="history-table-row">
                    <td class="font-mono text-xs text-muted" style="white-space: nowrap;">${escapeHtml(dateStr)}</td>
                    <td>
                        <div>
                            <strong>${escapeHtml(rec.item_name || rec.sku)}</strong>
                            <div class="font-mono text-xs text-primary" style="margin-top: 2px;">${escapeHtml(rec.sku)}</div>
                        </div>
                    </td>
                    <td>${typeBadge}</td>
                    <td>
                        <span class="wh-code-pill">${escapeHtml(rec.warehouse_code || "MULTI")}</span>
                    </td>
                    <td class="text-center">${deltaHtml}</td>
                    <td class="text-center font-bold">${(rec.new_stock ?? 0).toLocaleString()}</td>
                    <td>
                        <div style="font-size: 0.82rem;">
                            <strong class="text-light">${escapeHtml(rec.initiated_by || "System")}</strong>
                            <p class="text-muted" style="margin: 2px 0 0 0; font-size: 0.76rem;">${escapeHtml(rec.notes || "Stock updated")}</p>
                        </div>
                    </td>
                </tr>
            `;
        }).join("");
    }

    if (historySearchInput) historySearchInput.addEventListener("input", renderHistoryTable);
    if (historyTypeFilter) historyTypeFilter.addEventListener("change", renderHistoryTable);
    if (refreshHistoryBtn) refreshHistoryBtn.addEventListener("click", () => fetchHistory(false));

    // =========================================================================
    // 9. SKU Stock Movement Timeline Modal
    // =========================================================================

    async function openSkuHistoryModal(sku) {
        if (!skuHistoryModal) return;
        activeHistorySku = sku;

        const item = inventoryItems.find(i => i.sku === sku);
        if (skuHistorySkuBadge) skuHistorySkuBadge.textContent = sku;
        if (skuHistoryItemName) skuHistoryItemName.textContent = item ? item.name : sku;
        if (skuHistoryCurrentStock) skuHistoryCurrentStock.textContent = item ? `${item.total_stock} Units` : "--";

        if (skuTimelineContainer) {
            skuTimelineContainer.innerHTML = `
                <div class="text-center py-5">
                    <div class="loading-spinner"></div>
                    <p class="mt-2 text-muted">Retrieving stock movement timeline for ${escapeHtml(sku)}...</p>
                </div>
            `;
        }

        skuHistoryModal.style.display = "flex";

        try {
            const res = await fetch(`/api/inventory/${encodeURIComponent(sku)}/history`);
            const payload = await res.json();

            if (!res.ok || !payload.success) {
                throw new Error(payload.error || "Failed to load item timeline.");
            }

            const movements = payload.data || [];
            if (!skuTimelineContainer) return;

            if (movements.length === 0) {
                skuTimelineContainer.innerHTML = `
                    <div class="text-center py-5 text-muted">
                        <p>No historical movements recorded yet for <strong>${escapeHtml(sku)}</strong>.</p>
                    </div>
                `;
                return;
            }

            skuTimelineContainer.innerHTML = movements.map(m => {
                const delta = parseInt(m.quantity_delta || 0, 10);
                const deltaPill = delta >= 0 
                    ? `<span class="change-pill-pos">+${delta} units</span>`
                    : `<span class="change-pill-neg">${delta} units</span>`;

                let typeBadge = "";
                let dotEmoji = "📦";
                if (m.movement_type === "auto_allocation") {
                    typeBadge = `<span class="movement-type-badge mv-auto-allocation">⚡ AI Auto-Allocation</span>`;
                    dotEmoji = "🤖";
                } else if (m.movement_type === "creation") {
                    typeBadge = `<span class="movement-type-badge mv-creation">✨ Initial Registration</span>`;
                    dotEmoji = "✨";
                } else {
                    typeBadge = `<span class="movement-type-badge mv-manual-adjustment">🛠️ Manual Adjustment</span>`;
                    dotEmoji = "✏️";
                }

                const dateStr = m.timestamp 
                    ? new Date(m.timestamp).toISOString().replace("T", " ").substring(0, 19) + " UTC"
                    : "Recent";

                return `
                    <div class="timeline-item">
                        <div class="timeline-dot">${dotEmoji}</div>
                        <div class="timeline-item-header">
                            <div style="display: flex; align-items: center; gap: 0.5rem;">
                                ${typeBadge}
                                <span class="wh-code-pill" style="font-size: 0.7rem;">${escapeHtml(m.warehouse_code || "ALL")}</span>
                            </div>
                            <span class="timeline-time">${escapeHtml(dateStr)}</span>
                        </div>
                        <div class="timeline-body mt-2">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 0.4rem;">
                                <div>
                                    <span class="text-muted" style="font-size: 0.75rem;">Delta:</span>
                                    ${deltaPill}
                                </div>
                                <div>
                                    <span class="text-muted" style="font-size: 0.75rem;">Resulting Stock:</span>
                                    <strong class="font-mono text-primary">${m.new_stock ?? 0}</strong>
                                </div>
                            </div>
                            <p style="margin: 0; font-size: 0.8rem; color: #cbd5e1;">${escapeHtml(m.notes || "")}</p>
                            <div class="text-muted" style="margin-top: 0.35rem; font-size: 0.72rem;">
                                Initiated by: <span class="text-light font-bold">${escapeHtml(m.initiated_by || "System")}</span>
                                ${m.reference_id ? `&bull; Ref: <code class="font-mono">${escapeHtml(m.reference_id)}</code>` : ""}
                            </div>
                        </div>
                    </div>
                `;
            }).join("");
        } catch (err) {
            console.error("Error loading item timeline:", err);
            if (skuTimelineContainer) {
                skuTimelineContainer.innerHTML = `
                    <div class="text-center py-4 text-danger">
                        <p>⚠️ Error loading timeline: ${escapeHtml(err.message)}</p>
                    </div>
                `;
            }
        }
    }

    function closeSkuHistoryModal() {
        if (skuHistoryModal) skuHistoryModal.style.display = "none";
        activeHistorySku = null;
    }

    if (closeSkuHistoryModalBtn) closeSkuHistoryModalBtn.addEventListener("click", closeSkuHistoryModal);

    // =========================================================================
    // 10. UI Helpers & Event Listeners
    // =========================================================================

    if (searchInput) searchInput.addEventListener("input", applyFiltersAndRender);
    if (clearSearchBtn) {
        clearSearchBtn.addEventListener("click", () => {
            searchInput.value = "";
            applyFiltersAndRender();
            searchInput.focus();
        });
    }
    if (categoryFilter) categoryFilter.addEventListener("change", applyFiltersAndRender);
    if (statusFilter) statusFilter.addEventListener("change", applyFiltersAndRender);
    if (refreshBtn) refreshBtn.addEventListener("click", () => fetchInventory(false));
    if (resetFiltersBtn) {
        resetFiltersBtn.addEventListener("click", () => {
            if (searchInput) searchInput.value = "";
            if (categoryFilter) categoryFilter.value = "";
            if (statusFilter) statusFilter.value = "";
            applyFiltersAndRender();
        });
    }

    // Modal dismiss on backdrop or Escape
    window.addEventListener("keydown", (e) => {
        if (e.key === "Escape") {
            closeAddModal();
            closeEditModal();
            closeSkuHistoryModal();
        }
    });

    [addItemModal, editStockModal, skuHistoryModal].forEach(modal => {
        if (modal) {
            modal.addEventListener("click", (e) => {
                if (e.target === modal) {
                    closeAddModal();
                    closeEditModal();
                    closeSkuHistoryModal();
                }
            });
        }
    });

    function setButtonLoading(btn, isLoading, text) {
        if (!btn) return;
        const spinner = btn.querySelector(".btn-spinner");
        const txt = btn.querySelector(".btn-text");
        btn.disabled = isLoading;
        if (spinner) spinner.style.display = isLoading ? "inline-block" : "none";
        if (txt && text) txt.textContent = text;
    }

    function showAlert(msg, type = "info") {
        if (!alertBanner || !alertText) return;
        alertText.textContent = msg;
        if (alertIcon) {
            alertIcon.textContent = type === "error" ? "❌" : (type === "warning" ? "⚠️" : (type === "success" ? "✅" : "ℹ️"));
        }
        alertBanner.className = `inventory-alert-banner alert-${type}`;
        alertBanner.style.display = "flex";
    }

    function showToast(msg, type = "success") {
        if (!toastElem || !toastMsg) return;
        toastMsg.textContent = msg;
        if (toastIcon) {
            toastIcon.textContent = type === "error" ? "❌" : (type === "warning" ? "⚠️" : "✅");
        }
        toastElem.className = `inventory-toast toast-${type}`;
        toastElem.style.display = "flex";
        setTimeout(() => {
            toastElem.style.display = "none";
        }, 3500);
    }

    function escapeHtml(str) {
        if (str === null || str === undefined) return "";
        return String(str)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // Expose functions to window for template inline handlers and external calls
    window.switchInventoryTab = switchInventoryTab;
    window.openAddModal = openAddModal;
    window.closeAddModal = closeAddModal;
    window.openEditStockModal = openEditStockModal;
    window.closeEditModal = closeEditModal;
    window.openSkuHistoryModal = openSkuHistoryModal;
    window.closeSkuHistoryModal = closeSkuHistoryModal;
    window.fetchAnalytics = fetchAnalytics;
    window.fetchHistory = fetchHistory;
    window.refreshInventory = () => fetchInventory(false);

    // Detect initial tab from container data-initial-tab or URL
    const container = document.getElementById("inventoryMgmtContainer");
    const initialTabFromAttr = container ? container.getAttribute("data-initial-tab") : "catalog";
    const urlParams = new URLSearchParams(window.location.search);
    const tabParam = urlParams.get("tab");
    const currentPath = window.location.pathname;

    let targetTab = initialTabFromAttr || "catalog";
    if (currentPath.includes("/analytics") || tabParam === "analytics") {
        targetTab = "analytics";
    } else if (currentPath.includes("/history") || currentPath.includes("/audit-trail") || tabParam === "history") {
        targetTab = "history";
    }

    switchInventoryTab(targetTab);

    // Initial Fetch for Catalog
    fetchInventory();
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", initInventory);
} else {
    initInventory();
}

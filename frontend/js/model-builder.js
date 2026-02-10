/* ── Currency Formatting Helpers ────────────────────────────────── */
const CURRENCY_KEYS = new Set(['value', 'mean', 'min', 'max', 'likely']);

function attachCurrencyPreview(inputId) {
    const input = document.getElementById(inputId);
    if (!input) return;
    let preview = input.nextElementSibling;
    if (!preview || !preview.classList.contains('currency-preview')) {
        preview = document.createElement('div');
        preview.className = 'currency-preview';
        input.parentNode.insertBefore(preview, input.nextSibling);
    }
    const update = () => {
        const num = parseFloat(input.value);
        preview.textContent = isNaN(num) ? '' : '$' + num.toLocaleString('en-US', { maximumFractionDigits: 0 });
    };
    input.addEventListener('input', update);
    input.addEventListener('blur', update);
    update();
}

/* ── Distribution parameter templates ───────────────────────────── */
const DIST_PARAMS = {
    FIXED:       [{ key: 'value', label: 'Value', default: 100000 }],
    NORMAL:      [{ key: 'mean', label: 'Mean', default: 100000 }, { key: 'std', label: 'Std Dev', default: 15000 }],
    LOGNORMAL:   [{ key: 'mean', label: 'Mean (ln)', default: 11 }, { key: 'std', label: 'Std Dev (ln)', default: 0.5 }],
    UNIFORM:     [{ key: 'min', label: 'Min', default: 50000 }, { key: 'max', label: 'Max', default: 150000 }],
    TRIANGULAR:  [{ key: 'min', label: 'Min', default: 50000 }, { key: 'likely', label: 'Likely', default: 100000 }, { key: 'max', label: 'Max', default: 150000 }],
    LOGISTIC:    [{ key: 'amplitude', label: 'Total Market', default: 1.0 }, { key: 'midpoint', label: 'Midpoint (month)', default: 12 }, { key: 'steepness', label: 'Steepness', default: 0.3 }],
    LINEAR:      [{ key: 'rate', label: 'Monthly Rate (e.g. 0.05)', default: 0.05 }, { key: 'amplitude', label: 'Scale Factor', default: 1.0 }],
};

const CHILD_RATIO_PARAMS = {
    FIXED:       [{ key: 'value', label: 'Ratio', default: 0.20 }],
    NORMAL:      [{ key: 'mean', label: 'Mean Ratio', default: 0.20 }, { key: 'std', label: 'Std Dev', default: 0.03 }],
    UNIFORM:     [{ key: 'min', label: 'Min Ratio', default: 0.10 }, { key: 'max', label: 'Max Ratio', default: 0.30 }],
    TRIANGULAR:  [{ key: 'min', label: 'Min', default: 0.10 }, { key: 'likely', label: 'Likely', default: 0.20 }, { key: 'max', label: 'Max', default: 0.30 }],
};

const CHILD_ABSOLUTE_PARAMS = {
    FIXED:       [{ key: 'value', label: 'Value', default: 50000 }],
    NORMAL:      [{ key: 'mean', label: 'Mean', default: 50000 }, { key: 'std', label: 'Std Dev', default: 5000 }],
    UNIFORM:     [{ key: 'min', label: 'Min', default: 30000 }, { key: 'max', label: 'Max', default: 70000 }],
    TRIANGULAR:  [{ key: 'min', label: 'Min', default: 30000 }, { key: 'likely', label: 'Likely', default: 50000 }, { key: 'max', label: 'Max', default: 70000 }],
};

const UNIT_VALUE_PARAMS = {
    FIXED:       [{ key: 'value', label: 'Unit Price ($)', default: 50 }],
    NORMAL:      [{ key: 'mean', label: 'Mean Price ($)', default: 50 }, { key: 'std', label: 'Std Dev', default: 5 }],
    LOGNORMAL:   [{ key: 'mean', label: 'Mean (ln)', default: 3.9 }, { key: 'std', label: 'Std Dev (ln)', default: 0.3 }],
    UNIFORM:     [{ key: 'min', label: 'Min Price ($)', default: 30 }, { key: 'max', label: 'Max Price ($)', default: 70 }],
    TRIANGULAR:  [{ key: 'min', label: 'Min', default: 30 }, { key: 'likely', label: 'Likely', default: 50 }, { key: 'max', label: 'Max', default: 70 }],
};

const MARKET_UNITS_PARAMS = {
    FIXED:       [{ key: 'value', label: 'Number of Units', default: 10000 }],
    NORMAL:      [{ key: 'mean', label: 'Mean Units', default: 10000 }, { key: 'std', label: 'Std Dev', default: 1000 }],
    LOGNORMAL:   [{ key: 'mean', label: 'Mean (ln)', default: 9.2 }, { key: 'std', label: 'Std Dev (ln)', default: 0.3 }],
    UNIFORM:     [{ key: 'min', label: 'Min Units', default: 5000 }, { key: 'max', label: 'Max Units', default: 15000 }],
    TRIANGULAR:  [{ key: 'min', label: 'Min', default: 5000 }, { key: 'likely', label: 'Likely', default: 10000 }, { key: 'max', label: 'Max', default: 15000 }],
};

const ADOPTION_LABEL_OVERRIDES = { amplitude: 'Scale Factor (0\u20131)' };

/* ── Render distribution parameter inputs ──────────────────────── */
function renderDistParams(containerId, distType, prefix, existingParams, labelOverrides) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    const isCurrency = prefix === 'amount';
    const params = DIST_PARAMS[distType] || [];
    params.forEach(p => {
        const val = existingParams && existingParams[p.key] !== undefined ? existingParams[p.key] : p.default;
        const label = (labelOverrides && labelOverrides[p.key]) || p.label;
        const div = document.createElement('div');
        div.className = 'form-group';
        div.innerHTML = `
            <label for="${prefix}-${p.key}">${label}</label>
            <input type="number" id="${prefix}-${p.key}" value="${val}" step="any">
        `;
        container.appendChild(div);
        if (isCurrency && CURRENCY_KEYS.has(p.key)) {
            setTimeout(() => attachCurrencyPreview(`${prefix}-${p.key}`), 0);
        }
    });
}

function renderChildDistParams(containerId, distType, prefix, existingParams, isRatio) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    const paramSet = isRatio ? CHILD_RATIO_PARAMS : CHILD_ABSOLUTE_PARAMS;
    const params = paramSet[distType] || DIST_PARAMS[distType] || [];
    params.forEach(p => {
        const val = existingParams && existingParams[p.key] !== undefined ? existingParams[p.key] : p.default;
        const div = document.createElement('div');
        div.className = 'form-group';
        div.innerHTML = `
            <label for="${prefix}-${p.key}">${p.label}</label>
            <input type="number" id="${prefix}-${p.key}" value="${val}" step="any">
        `;
        container.appendChild(div);
        if (!isRatio && CURRENCY_KEYS.has(p.key)) {
            setTimeout(() => attachCurrencyPreview(`${prefix}-${p.key}`), 0);
        }
    });
}

function getDistFromInputs(distTypeSelectId, paramsContainerId) {
    const typeEl = document.getElementById(distTypeSelectId);
    if (!typeEl) return null;
    const distType = typeEl.value;
    const params = {};
    const allParamSets = [DIST_PARAMS, CHILD_RATIO_PARAMS, CHILD_ABSOLUTE_PARAMS];
    // Collect all known keys for this dist type
    const knownKeys = new Set();
    allParamSets.forEach(ps => {
        if (ps[distType]) ps[distType].forEach(p => knownKeys.add(p.key));
    });
    knownKeys.forEach(key => {
        const input = document.getElementById(
            paramsContainerId.replace('-params', '') + '-' + key
        );
        if (input) params[key] = parseFloat(input.value);
    });
    return { type: distType, params };
}

function renderSpecificDistParams(containerId, distType, prefix, existingParams, paramSet) {
    const container = document.getElementById(containerId);
    if (!container) return;
    container.innerHTML = '';
    const isCurrency = prefix === 'unit-value' || prefix === 'market-units';
    const params = paramSet[distType] || [];
    params.forEach(p => {
        const val = existingParams && existingParams[p.key] !== undefined ? existingParams[p.key] : p.default;
        const div = document.createElement('div');
        div.className = 'form-group';
        div.innerHTML = `
            <label for="${prefix}-${p.key}">${p.label}</label>
            <input type="number" id="${prefix}-${p.key}" value="${val}" step="any">
        `;
        container.appendChild(div);
        if (isCurrency && CURRENCY_KEYS.has(p.key)) {
            setTimeout(() => attachCurrencyPreview(`${prefix}-${p.key}`), 0);
        }
    });
}

function getSpecificDistFromInputs(distTypeSelectId, prefix, paramSet) {
    const typeEl = document.getElementById(distTypeSelectId);
    if (!typeEl) return null;
    const distType = typeEl.value;
    const params = {};
    const knownParams = paramSet[distType] || [];
    knownParams.forEach(p => {
        const input = document.getElementById(`${prefix}-${p.key}`);
        if (input) params[p.key] = parseFloat(input.value);
    });
    return { type: distType, params };
}

function getDeterministicEstimate(dist) {
    if (!dist || !dist.params) return 0;
    const p = dist.params;
    switch (dist.type) {
        case 'FIXED': return p.value || 0;
        case 'NORMAL': return p.mean || 0;
        case 'LOGNORMAL': return Math.exp((p.mean || 0) + (p.std || 0) ** 2 / 2);
        case 'UNIFORM': return ((p.min || 0) + (p.max || 0)) / 2;
        case 'TRIANGULAR': return ((p.min || 0) + (p.likely || 0) + (p.max || 0)) / 3;
        default: return 0;
    }
}

function updateEstimatedTotal() {
    const uvDist = getSpecificDistFromInputs('unit-value-dist-type', 'unit-value', UNIT_VALUE_PARAMS);
    const muDist = getSpecificDistFromInputs('market-units-dist-type', 'market-units', MARKET_UNITS_PARAMS);
    const total = getDeterministicEstimate(uvDist) * getDeterministicEstimate(muDist);
    const el = document.getElementById('unit-total-value');
    if (el) el.textContent = '$' + total.toLocaleString('en-US', { maximumFractionDigits: 0 });
}

function toggleAmountEntryMode() {
    const mode = document.getElementById('amount-entry-mode').value;
    document.getElementById('amount-total-mode').style.display = mode === 'total' ? 'block' : 'none';
    document.getElementById('amount-unit-mode').style.display = mode === 'unit' ? 'block' : 'none';
    updateFormulaBar();
}

/* ── Stream List ───────────────────────────────────────────────── */
function renderStreamList(model) {
    const container = document.getElementById('stream-list');
    if (!container) return;
    container.innerHTML = '';

    if (!model || !model.streams || model.streams.length === 0) {
        container.innerHTML = '<p class="text-muted">No streams yet. Click "+ Add Stream" to begin.</p>';
        return;
    }

    const streams = Array.isArray(model.streams) ? model.streams : Object.values(model.streams);

    streams.forEach(stream => {
        const badgeClass = stream.stream_type === 'REVENUE' ? 'badge-revenue' : 'badge-cost';
        const endLabel = stream.end_month === null || stream.end_month === undefined ? 'Perpetual' : `Month ${stream.end_month}`;
        const parentLabel = stream.parent_stream_id ? ` (child of ${stream.parent_stream_id})` : '';

        const div = document.createElement('div');
        div.className = 'stream-item';
        div.setAttribute('data-stream-id', stream.id);
        div.innerHTML = `
            <div class="stream-drag-handle" title="Drag to reorder">\u22EE\u22EE</div>
            <div class="stream-content">
                <div class="stream-name">
                    <span class="stream-type-badge ${badgeClass}">${stream.stream_type}</span>
                    ${stream.name}
                </div>
                <div class="stream-meta">Month ${stream.start_month} - ${endLabel}${parentLabel}</div>
                <div class="stream-actions">
                    <button class="btn btn-sm" onclick="editStream('${stream.id}')">Edit</button>
                    <button class="btn btn-sm" onclick="duplicateStream('${stream.id}')">Clone</button>
                    <button class="btn btn-sm btn-danger" onclick="deleteStream('${stream.id}')">Delete</button>
                </div>
            </div>
        `;
        container.appendChild(div);
    });

    initStreamSortable();
}

let sortableInstance = null;

function initStreamSortable() {
    const container = document.getElementById('stream-list');
    if (!container || typeof Sortable === 'undefined') return;
    if (sortableInstance) sortableInstance.destroy();
    if (!container.querySelector('.stream-item')) return;

    sortableInstance = Sortable.create(container, {
        animation: 150,
        handle: '.stream-drag-handle',
        ghostClass: 'stream-item-ghost',
        dragClass: 'stream-item-drag',
        onEnd: async function () {
            const items = container.querySelectorAll('.stream-item');
            const newOrder = Array.from(items).map(el => el.getAttribute('data-stream-id'));
            try {
                currentModel = await api.put('/streams/reorder', { order: newOrder });
            } catch (e) {
                alert('Error reordering: ' + e.message);
                renderModel();
            }
        }
    });
}

/* ── Stream Modal ──────────────────────────────────────────────── */
let editingStreamId = null;

function updateParentFields() {
    const parentVal = document.getElementById('stream-parent').value;
    const isChild = parentVal !== '';
    document.getElementById('root-stream-fields').style.display = isChild ? 'none' : 'block';
    document.getElementById('child-stream-fields').style.display = isChild ? 'block' : 'none';
    updateFormulaBar();
}

function updateFormulaBar() {
    const isChild = document.getElementById('stream-parent').value !== '';
    const hasAdoption = document.getElementById('has-adoption').checked;
    const entryMode = document.getElementById('amount-entry-mode').value;

    if (isChild) {
        const isRatio = document.getElementById('amount-is-ratio').checked;
        document.getElementById('formula-label').textContent = 'Child Cashflow =';
        document.getElementById('formula-amount').textContent = isRatio ? 'Parent Revenue \u00d7 Price Ratio \u00d7 Conv. Rate' : 'Amount \u00d7 Conv. Rate';
        document.getElementById('formula-adoption-op').style.display = 'none';
        document.getElementById('formula-adoption').style.display = 'none';
    } else {
        document.getElementById('formula-label').textContent = 'Monthly Cashflow =';
        document.getElementById('formula-amount').textContent = entryMode === 'unit' ? 'Unit Value \u00d7 Market Units' : 'Base Amount';
        document.getElementById('formula-adoption-op').style.display = hasAdoption ? 'inline' : 'none';
        document.getElementById('formula-adoption').style.display = hasAdoption ? 'inline' : 'none';
    }
}

function updateChildAmountLabels(existingParams) {
    const isRatio = document.getElementById('amount-is-ratio').checked;
    document.getElementById('child-amount-heading').textContent = isRatio ? 'Price Ratio' : 'Absolute Value';
    document.getElementById('child-amount-help').textContent = isRatio
        ? 'Fraction of the parent stream\'s value. Use a distribution to model uncertainty.'
        : 'Fixed dollar amount per event. Use a distribution to model uncertainty.';
    const distType = document.getElementById('child-amount-dist-type').value;
    renderChildDistParams('child-amount-params', distType, 'child-amount', existingParams || null, isRatio);
    updateFormulaBar();
}

function showStreamModal(streamId = null) {
    editingStreamId = streamId;
    const modal = document.getElementById('modal-stream');
    const title = document.getElementById('modal-stream-title');

    // Populate parent dropdown
    const parentSelect = document.getElementById('stream-parent');
    parentSelect.innerHTML = '<option value="">None (root stream)</option>';
    if (currentModel && currentModel.streams) {
        const streams = Array.isArray(currentModel.streams) ? currentModel.streams : Object.values(currentModel.streams);
        streams.forEach(s => {
            if (s.id !== streamId) {
                parentSelect.innerHTML += `<option value="${s.id}">${s.name}</option>`;
            }
        });
    }

    if (streamId && currentModel) {
        title.textContent = 'Edit Stream';
        const streams = Array.isArray(currentModel.streams) ? currentModel.streams : Object.values(currentModel.streams);
        const stream = streams.find(s => s.id === streamId);
        if (stream) {
            document.getElementById('stream-id').value = stream.id;
            document.getElementById('stream-id').disabled = true;
            document.getElementById('stream-name').value = stream.name;
            document.getElementById('stream-type').value = stream.stream_type;
            document.getElementById('stream-start').value = stream.start_month;
            document.getElementById('stream-end').value = stream.end_month ?? '';
            document.getElementById('stream-parent').value = stream.parent_stream_id || '';

            if (stream.parent_stream_id) {
                // Child stream
                document.getElementById('amount-is-ratio').checked = stream.amount_is_ratio !== false;
                document.getElementById('child-amount-dist-type').value = stream.amount.type;
                document.getElementById('child-conversion-rate').value = stream.conversion_rate ?? 1.0;
                document.getElementById('child-trigger-delay').value = stream.trigger_delay_months ?? 0;
                document.getElementById('child-periodicity').value = stream.periodicity_months ?? '';
                updateChildAmountLabels(stream.amount.params);
            } else {
                // Root stream - detect unit value mode
                if (stream.unit_value && stream.market_units) {
                    document.getElementById('amount-entry-mode').value = 'unit';
                    document.getElementById('unit-value-dist-type').value = stream.unit_value.type;
                    renderSpecificDistParams('unit-value-params', stream.unit_value.type, 'unit-value', stream.unit_value.params, UNIT_VALUE_PARAMS);
                    document.getElementById('market-units-dist-type').value = stream.market_units.type;
                    renderSpecificDistParams('market-units-params', stream.market_units.type, 'market-units', stream.market_units.params, MARKET_UNITS_PARAMS);
                    toggleAmountEntryMode();
                    updateEstimatedTotal();
                } else {
                    document.getElementById('amount-entry-mode').value = 'total';
                    document.getElementById('amount-dist-type').value = stream.amount.type;
                    renderDistParams('amount-params', stream.amount.type, 'amount', stream.amount.params);
                    toggleAmountEntryMode();
                }

                if (stream.adoption_curve) {
                    document.getElementById('has-adoption').checked = true;
                    document.getElementById('adoption-section').style.display = 'block';
                    document.getElementById('adoption-dist-type').value = stream.adoption_curve.type;
                    renderDistParams('adoption-params', stream.adoption_curve.type, 'adoption', stream.adoption_curve.params, ADOPTION_LABEL_OVERRIDES);
                } else {
                    document.getElementById('has-adoption').checked = false;
                    document.getElementById('adoption-section').style.display = 'none';
                }
            }

            updateParentFields();
        }
    } else {
        title.textContent = 'Add Stream';
        document.getElementById('stream-id').value = '';
        document.getElementById('stream-id').disabled = false;
        document.getElementById('stream-name').value = '';
        document.getElementById('stream-type').value = 'REVENUE';
        document.getElementById('stream-start').value = '0';
        document.getElementById('stream-end').value = '';
        document.getElementById('stream-parent').value = '';
        document.getElementById('amount-entry-mode').value = 'total';
        document.getElementById('amount-dist-type').value = 'FIXED';
        renderDistParams('amount-params', 'FIXED', 'amount', null);
        document.getElementById('unit-value-dist-type').value = 'FIXED';
        renderSpecificDistParams('unit-value-params', 'FIXED', 'unit-value', null, UNIT_VALUE_PARAMS);
        document.getElementById('market-units-dist-type').value = 'FIXED';
        renderSpecificDistParams('market-units-params', 'FIXED', 'market-units', null, MARKET_UNITS_PARAMS);
        toggleAmountEntryMode();
        document.getElementById('has-adoption').checked = false;
        document.getElementById('adoption-section').style.display = 'none';
        // Reset child fields
        document.getElementById('amount-is-ratio').checked = true;
        document.getElementById('child-amount-dist-type').value = 'FIXED';
        renderChildDistParams('child-amount-params', 'FIXED', 'child-amount', null, true);
        document.getElementById('child-conversion-rate').value = '1.0';
        document.getElementById('child-trigger-delay').value = '0';
        document.getElementById('child-periodicity').value = '';
        updateParentFields();
    }

    modal.classList.add('active');
}

function closeStreamModal() {
    document.getElementById('modal-stream').classList.remove('active');
    editingStreamId = null;
}

function editStream(streamId) {
    showStreamModal(streamId);
}

async function deleteStream(streamId) {
    if (!confirm(`Delete stream "${streamId}"?`)) return;
    try {
        currentModel = await api.delete(`/streams/${streamId}`);
        renderModel();
    } catch (e) {
        alert('Error deleting stream: ' + e.message);
    }
}

async function duplicateStream(streamId) {
    if (!currentModel) return;
    const streams = Array.isArray(currentModel.streams) ? currentModel.streams : Object.values(currentModel.streams);
    const src = streams.find(s => s.id === streamId);
    if (!src) { alert('Stream not found.'); return; }

    let copyId = streamId + '_copy';
    let counter = 1;
    while (streams.some(s => s.id === copyId)) {
        copyId = `${streamId}_copy${counter}`;
        counter++;
    }

    const data = {
        id: copyId,
        name: src.name + ' (Copy)',
        stream_type: src.stream_type,
        start_month: src.start_month,
        end_month: src.end_month,
        amount: src.amount,
        adoption_curve: src.adoption_curve,
        parent_stream_id: src.parent_stream_id,
        conversion_rate: src.conversion_rate,
        trigger_delay_months: src.trigger_delay_months,
        periodicity_months: src.periodicity_months,
        amount_is_ratio: src.amount_is_ratio,
        unit_value: src.unit_value,
        market_units: src.market_units,
    };

    try {
        currentModel = await api.post('/streams', data);
        renderModel();
        showStatus(`Stream "${src.name}" cloned.`);
    } catch (e) {
        alert('Error duplicating stream: ' + e.message);
    }
}

async function saveStream(e) {
    e.preventDefault();

    const parentId = document.getElementById('stream-parent').value || null;
    const isChild = parentId !== null;

    const streamData = {
        id: document.getElementById('stream-id').value.trim(),
        name: document.getElementById('stream-name').value.trim(),
        stream_type: document.getElementById('stream-type').value,
        start_month: parseInt(document.getElementById('stream-start').value) || 0,
        end_month: document.getElementById('stream-end').value ? parseInt(document.getElementById('stream-end').value) : null,
        parent_stream_id: parentId,
        adoption_curve: null,
        conversion_rate: 1.0,
        trigger_delay_months: 0,
        periodicity_months: null,
        amount_is_ratio: true,
    };

    if (!streamData.id || !streamData.name) {
        alert('Stream ID and Name are required.');
        return;
    }

    if (isChild) {
        streamData.amount = getDistFromInputs('child-amount-dist-type', 'child-amount-params');
        streamData.amount_is_ratio = document.getElementById('amount-is-ratio').checked;
        streamData.conversion_rate = parseFloat(document.getElementById('child-conversion-rate').value) || 1.0;
        streamData.trigger_delay_months = parseInt(document.getElementById('child-trigger-delay').value) || 0;
        const periodicity = document.getElementById('child-periodicity').value;
        streamData.periodicity_months = periodicity ? parseInt(periodicity) : null;
    } else {
        const entryMode = document.getElementById('amount-entry-mode').value;
        if (entryMode === 'unit') {
            // Unit value x market units mode
            streamData.unit_value = getSpecificDistFromInputs('unit-value-dist-type', 'unit-value', UNIT_VALUE_PARAMS);
            streamData.market_units = getSpecificDistFromInputs('market-units-dist-type', 'market-units', MARKET_UNITS_PARAMS);
            // Set amount to a dummy FIXED 0 (backend uses unit_value * market_units)
            streamData.amount = { type: 'FIXED', params: { value: 0 } };
        } else {
            streamData.amount = getDistFromInputs('amount-dist-type', 'amount-params');
        }
        if (document.getElementById('has-adoption').checked) {
            streamData.adoption_curve = getDistFromInputs('adoption-dist-type', 'adoption-params');
        }
    }

    try {
        if (editingStreamId) {
            currentModel = await api.put(`/streams/${editingStreamId}`, streamData);
        } else {
            currentModel = await api.post('/streams', streamData);
        }
        closeStreamModal();
        renderModel();
    } catch (e) {
        alert('Error saving stream: ' + e.message);
    }
}

/* ── Cashflows Tab ─────────────────────────────────────────────── */
function renderCashflowsTab(model) {
    const container = document.getElementById('cashflows-container');
    if (!container) return;
    container.innerHTML = '';

    if (!model || !model.streams) {
        container.innerHTML = '<p class="text-muted">Load or create a model to see cashflows.</p>';
        return;
    }

    const streams = Array.isArray(model.streams) ? model.streams : Object.values(model.streams);
    if (streams.length === 0) {
        container.innerHTML = '<p class="text-muted">Add streams to see cashflow previews.</p>';
        return;
    }

    // Combined chart section
    let html = `
        <div class="param-section">
            <h3>Combined Stream Cashflows</h3>
            <p class="text-muted">Click legend items to toggle streams on/off.</p>
            <button class="btn btn-sm" id="btn-run-combined-preview">Generate Preview</button>
            <div class="preview-canvas-container">
                <canvas id="combined-cashflow-chart" height="250"></canvas>
            </div>
        </div>
    `;

    // Individual stream sections
    streams.forEach(stream => {
        const badgeClass = stream.stream_type === 'REVENUE' ? 'badge-revenue' : 'badge-cost';
        const startM = stream.start_month;
        const endM = stream.end_month;

        html += `<div class="param-section">`;
        html += `<h3><span class="stream-type-badge ${badgeClass}">${stream.stream_type}</span> ${stream.name}</h3>`;

        if (stream.parent_stream_id) {
            html += `<p class="text-muted">Child of: ${stream.parent_stream_id} | `;
            html += `Conv: ${(stream.conversion_rate * 100).toFixed(0)}% | `;
            html += `Delay: ${stream.trigger_delay_months}mo | `;
            html += stream.periodicity_months ? `Renews every ${stream.periodicity_months}mo` : 'Concurrent';
            html += `</p>`;
            html += `<p class="text-muted">Amount: ${stream.amount_is_ratio ? 'Ratio' : 'Absolute'} ${stream.amount.type} ${JSON.stringify(stream.amount.params)}</p>`;
            html += `<button class="btn btn-sm" onclick="previewChildCashflow('${stream.id}')">Preview Cashflow</button>`;
            html += `<div class="preview-canvas-container"><canvas id="preview-${stream.id}-cashflow" height="150"></canvas></div>`;
        } else {
            if (stream.unit_value && stream.market_units) {
                html += `<p class="text-muted">Unit Value: ${stream.unit_value.type} ${JSON.stringify(stream.unit_value.params)}</p>`;
                html += `<p class="text-muted">Market Units: ${stream.market_units.type} ${JSON.stringify(stream.market_units.params)}</p>`;
                const uvEst = getDeterministicEstimate(stream.unit_value);
                const muEst = getDeterministicEstimate(stream.market_units);
                html += `<p class="text-muted"><strong>Estimated Total: $${(uvEst * muEst).toLocaleString('en-US', { maximumFractionDigits: 0 })}</strong></p>`;
            } else {
                html += `<p class="text-muted">Amount: ${stream.amount.type} ${JSON.stringify(stream.amount.params)}</p>`;
            }
            html += `<button class="btn btn-sm" onclick="previewDistribution('${stream.id}', 'amount', ${JSON.stringify(stream.amount).replace(/"/g, '&quot;')}, ${startM}, ${endM === null || endM === undefined ? 'null' : endM})">Preview Amount</button>`;
            html += `<div class="preview-canvas-container"><canvas id="preview-${stream.id}-amount" height="150"></canvas></div>`;

            if (stream.adoption_curve) {
                html += `<p class="text-muted mt-2">Adoption: ${stream.adoption_curve.type} ${JSON.stringify(stream.adoption_curve.params)}</p>`;
                html += `<button class="btn btn-sm" onclick="previewDistribution('${stream.id}', 'adoption', ${JSON.stringify(stream.adoption_curve).replace(/"/g, '&quot;')}, ${startM}, ${endM === null || endM === undefined ? 'null' : endM})">Preview Adoption</button>`;
                html += `<div class="preview-canvas-container"><canvas id="preview-${stream.id}-adoption" height="150"></canvas></div>`;
            }
        }

        html += `</div>`;
    });

    container.innerHTML = html;

    // Wire up combined preview button
    const btn = document.getElementById('btn-run-combined-preview');
    if (btn) {
        btn.addEventListener('click', runCombinedPreview);
    }
}

async function runCombinedPreview() {
    if (!currentModel) return;
    try {
        const results = await api.post('/calculate/deterministic');
        if (results && results.stream_details) {
            const streams = Array.isArray(currentModel.streams) ? currentModel.streams : Object.values(currentModel.streams);
            const streamMeta = streams.map(s => ({
                id: s.id,
                name: s.name,
                type: s.stream_type,
            }));
            chartManager.renderCombinedCashflowChart('combined-cashflow-chart', results.stream_details, streamMeta);
        }
    } catch (e) {
        alert('Error generating preview: ' + e.message);
    }
}

async function previewChildCashflow(streamId) {
    try {
        const results = await api.post('/calculate/deterministic');
        if (results && results.stream_details && results.stream_details[streamId]) {
            const cfs = results.stream_details[streamId];
            const previewData = cfs.map((v, i) => ({ month: i, value: v }));
            chartManager.renderDistributionPreview(`preview-${streamId}-cashflow`, previewData);
        }
    } catch (e) {
        alert('Error generating preview: ' + e.message);
    }
}

async function previewDistribution(streamId, paramName, dist, startMonth, endMonth) {
    try {
        const months = currentModel && currentModel.settings ? currentModel.settings.forecast_months : 60;
        const payload = { distribution: dist, months, start_month: startMonth };
        if (endMonth !== null && endMonth !== undefined) {
            payload.end_month = endMonth;
        }
        const result = await api.post('/preview-distribution', payload);
        chartManager.renderDistributionPreview(`preview-${streamId}-${paramName}`, result.preview);
    } catch (e) {
        alert('Error generating preview: ' + e.message);
    }
}

/* ── Discount Rate & Escalation Rate Params ────────────────────── */
function toggleCalculationMode() {
    const mode = document.getElementById('calculation-mode').value;
    const drSection = document.getElementById('discount-rate-section');
    const tgSection = document.getElementById('terminal-growth-section');
    const helpText = document.getElementById('calc-mode-help');
    if (mode === 'IRR') {
        drSection.style.display = 'none';
        tgSection.style.display = 'none';
        helpText.textContent = 'IRR finds the discount rate that makes NPV = 0. No discount rate or terminal growth needed.';
    } else {
        drSection.style.display = 'block';
        tgSection.style.display = 'block';
        helpText.textContent = 'NPV discounts future cashflows to present value. IRR finds the rate that makes NPV = 0.';
    }
}

function setupDiscountRateInputs() {
    const typeSelect = document.getElementById('dr-dist-type');
    if (!typeSelect) return;

    // Calculation mode toggle
    const calcModeSelect = document.getElementById('calculation-mode');
    if (calcModeSelect) {
        calcModeSelect.addEventListener('change', toggleCalculationMode);
    }

    typeSelect.addEventListener('change', () => {
        renderDistParams('dr-params', typeSelect.value, 'dr', null);
    });
    renderDistParams('dr-params', 'NORMAL', 'dr', { mean: 0.12, std: 0.02 });

    // Escalation rate
    const escToggle = document.getElementById('has-escalation');
    const escSection = document.getElementById('escalation-section');
    const escTypeSelect = document.getElementById('esc-dist-type');

    if (escToggle && escSection) {
        escToggle.addEventListener('change', function () {
            escSection.style.display = this.checked ? 'block' : 'none';
        });
    }
    if (escTypeSelect) {
        escTypeSelect.addEventListener('change', () => {
            renderDistParams('esc-params', escTypeSelect.value, 'esc', null);
        });
        renderDistParams('esc-params', 'NORMAL', 'esc', { mean: 0.03, std: 0.01 });
    }
}

/* ── Event bindings for dynamic elements ──────────────────────── */
function setupModelBuilderEvents() {
    // Amount entry mode toggle
    document.getElementById('amount-entry-mode').addEventListener('change', toggleAmountEntryMode);

    // Root stream distribution type changes
    document.getElementById('amount-dist-type').addEventListener('change', function () {
        renderDistParams('amount-params', this.value, 'amount', null);
    });
    renderDistParams('amount-params', 'FIXED', 'amount', null);

    // Unit value distribution type changes
    document.getElementById('unit-value-dist-type').addEventListener('change', function () {
        renderSpecificDistParams('unit-value-params', this.value, 'unit-value', null, UNIT_VALUE_PARAMS);
        updateEstimatedTotal();
    });
    renderSpecificDistParams('unit-value-params', 'FIXED', 'unit-value', null, UNIT_VALUE_PARAMS);

    // Market units distribution type changes
    document.getElementById('market-units-dist-type').addEventListener('change', function () {
        renderSpecificDistParams('market-units-params', this.value, 'market-units', null, MARKET_UNITS_PARAMS);
        updateEstimatedTotal();
    });
    renderSpecificDistParams('market-units-params', 'FIXED', 'market-units', null, MARKET_UNITS_PARAMS);

    // Update estimated total when inputs change
    document.getElementById('unit-value-params').addEventListener('input', updateEstimatedTotal);
    document.getElementById('market-units-params').addEventListener('input', updateEstimatedTotal);

    document.getElementById('adoption-dist-type').addEventListener('change', function () {
        renderDistParams('adoption-params', this.value, 'adoption', null, ADOPTION_LABEL_OVERRIDES);
    });
    renderDistParams('adoption-params', 'LOGISTIC', 'adoption', null, ADOPTION_LABEL_OVERRIDES);

    // Child stream distribution type changes
    document.getElementById('child-amount-dist-type').addEventListener('change', function () {
        const isRatio = document.getElementById('amount-is-ratio').checked;
        renderChildDistParams('child-amount-params', this.value, 'child-amount', null, isRatio);
    });
    renderChildDistParams('child-amount-params', 'FIXED', 'child-amount', null, true);

    // Amount is ratio toggle
    document.getElementById('amount-is-ratio').addEventListener('change', updateChildAmountLabels);

    // Adoption toggle
    document.getElementById('has-adoption').addEventListener('change', function () {
        document.getElementById('adoption-section').style.display = this.checked ? 'block' : 'none';
        updateFormulaBar();
    });

    // Parent stream change
    document.getElementById('stream-parent').addEventListener('change', updateParentFields);

    // Stream form submit
    document.getElementById('form-stream').addEventListener('submit', saveStream);

    // Modal close buttons
    document.getElementById('close-stream-modal').addEventListener('click', closeStreamModal);
    document.getElementById('btn-cancel-stream').addEventListener('click', closeStreamModal);

    setupDiscountRateInputs();
}

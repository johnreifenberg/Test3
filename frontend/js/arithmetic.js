/**
 * Streams Arithmetic Engine - Simplified Drag & Drop Interface
 * Evaluates formulas on stream cashflows from last calculation results.
 */

class ArithmeticEngine {
    constructor() {
        this.formulas = [];  // [{name, formula, cashflows}]
        this.streamDetails = null;  // From last calculation
        this.currentFormula = [];  // Array of tokens: {type: 'stream'|'operator', value: string}
    }

    setStreamDetails(details) {
        this.streamDetails = details;
    }

    hasStreamData() {
        return this.streamDetails && this.streamDetails.length > 0;
    }

    getStreams() {
        if (!this.streamDetails) return [];
        return this.streamDetails.map(s => ({
            name: s.stream_name,
            type: s.stream_type || 'REVENUE'
        }));
    }

    addToken(type, value) {
        this.currentFormula.push({type, value});
        return this.buildFormulaString();
    }

    clearFormula() {
        this.currentFormula = [];
        return '';
    }

    buildFormulaString() {
        if (this.currentFormula.length === 0) return '';
        return this.currentFormula.map(token => {
            if (token.type === 'stream') {
                return token.value;  // Stream name (may have spaces)
            }
            return ` ${token.value} `;  // Operator with spaces
        }).join('').trim();
    }

    evaluateFormula(formula) {
        /**
         * Evaluate formula month-by-month using stream cashflows.
         * Returns: {cashflows: number[], error: string}
         */
        if (!this.streamDetails) {
            return {cashflows: null, error: "No calculation results available. Run a calculation first."};
        }

        if (!formula || formula.trim() === '') {
            return {cashflows: null, error: "Formula is empty"};
        }

        // Build lookup: stream_name -> cashflows array
        const streamCashflows = {};
        for (const detail of this.streamDetails) {
            streamCashflows[detail.stream_name] = detail.cashflows;
        }

        // Validate all stream references exist
        const streamNames = Object.keys(streamCashflows);
        for (const name of streamNames) {
            if (!formula.includes(name)) continue;
            // Check if the stream name is properly isolated (not part of another word)
            const regex = new RegExp('\\b' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b');
            if (!regex.test(formula)) {
                // Stream name exists but not as a complete word
                continue;
            }
        }

        // Determine result length (max of all streams)
        let maxLength = Math.max(...Object.values(streamCashflows).map(cf => cf.length));

        // Evaluate month by month
        const result = [];
        for (let month = 0; month < maxLength; month++) {
            // Build expression with values for this month
            let expr = formula;

            // Replace stream names with values (longest names first to avoid partial replacements)
            const sortedNames = Object.keys(streamCashflows).sort((a, b) => b.length - a.length);
            for (const name of sortedNames) {
                const cfs = streamCashflows[name];
                const value = month < cfs.length ? cfs[month] : 0;
                // Use regex to replace whole words only
                const regex = new RegExp('\\b' + name.replace(/[.*+?^${}()|[\]\\]/g, '\\$&') + '\\b', 'g');
                expr = expr.replace(regex, `(${value})`);
            }

            try {
                // Evaluate using Function constructor (safer than eval)
                const calculated = new Function('return ' + expr)();
                result.push(calculated);
            } catch (e) {
                return {cashflows: null, error: `Evaluation error at month ${month}: ${e.message}`};
            }
        }

        return {cashflows: result, error: null};
    }

    saveFormula(name, formula) {
        const result = this.evaluateFormula(formula);
        if (result.error) {
            return {success: false, error: result.error};
        }

        // Check for duplicate names
        if (this.formulas.find(f => f.name === name)) {
            return {success: false, error: `Formula "${name}" already exists`};
        }

        this.formulas.push({name, formula, cashflows: result.cashflows});
        syncFormulasToBackend();
        return {success: true};
    }

    removeFormula(name) {
        this.formulas = this.formulas.filter(f => f.name !== name);
        syncFormulasToBackend();
    }

    getFormulas() {
        return this.formulas;
    }

    clearFormulas() {
        this.formulas = [];
    }

    loadFormulas(formulas) {
        this.formulas = [];
        if (!formulas || !Array.isArray(formulas)) {
            return;
        }
        for (const f of formulas) {
            if (f.name && f.formula) {
                this.formulas.push({
                    name: f.name,
                    formula: f.formula,
                    cashflows: null
                });
            }
        }
    }

    exportFormulas() {
        return this.formulas.map(f => ({
            name: f.name,
            formula: f.formula
        }));
    }

    recalculateAll() {
        const updatedFormulas = [];
        for (const formula of this.formulas) {
            const result = this.evaluateFormula(formula.formula);
            updatedFormulas.push({
                name: formula.name,
                formula: formula.formula,
                cashflows: result.cashflows || []
            });
        }
        this.formulas = updatedFormulas;
    }
}

// Global instance
const arithmeticEngine = new ArithmeticEngine();

/**
 * UI Management
 */
function initArithmeticTab() {
    renderAvailableStreams();
    renderFormulasListNew();
    setupDragAndDrop();
    setupOperatorButtons();
    setupSaveButton();
}

function renderAvailableStreams() {
    const container = document.getElementById('available-streams');
    const noCalcWarning = document.getElementById('arithmetic-no-calc');

    if (!arithmeticEngine.hasStreamData()) {
        container.innerHTML = '<p class="help-text">Run a calculation to load streams</p>';
        noCalcWarning.style.display = 'block';
        return;
    }

    noCalcWarning.style.display = 'none';
    container.innerHTML = '';

    const streams = arithmeticEngine.getStreams();
    for (const stream of streams) {
        const div = document.createElement('div');
        div.className = 'stream-item';
        div.classList.add(stream.type.toLowerCase());
        div.textContent = stream.name;
        div.draggable = true;
        div.dataset.streamName = stream.name;

        // Drag events
        div.addEventListener('dragstart', (e) => {
            e.dataTransfer.setData('text/plain', stream.name);
            e.dataTransfer.effectAllowed = 'copy';
        });

        // Click to add
        div.addEventListener('click', () => {
            addStreamToFormula(stream.name);
        });

        container.appendChild(div);
    }
}

function setupDragAndDrop() {
    const display = document.getElementById('formula-display');

    display.addEventListener('dragover', (e) => {
        e.preventDefault();
        display.classList.add('drag-over');
    });

    display.addEventListener('dragleave', () => {
        display.classList.remove('drag-over');
    });

    display.addEventListener('drop', (e) => {
        e.preventDefault();
        display.classList.remove('drag-over');
        const streamName = e.dataTransfer.getData('text/plain');
        if (streamName) {
            addStreamToFormula(streamName);
        }
    });
}

function setupOperatorButtons() {
    document.querySelectorAll('.op-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const op = btn.dataset.op;
            if (op === 'clear') {
                clearFormulaDisplay();
            } else {
                addOperatorToFormula(op);
            }
        });
    });
}

function setupSaveButton() {
    document.getElementById('btn-save-formula').addEventListener('click', () => {
        const name = document.getElementById('formula-name-new').value.trim();
        const formula = arithmeticEngine.buildFormulaString();

        if (!name) {
            alert('Please enter a formula name');
            return;
        }

        if (!formula) {
            alert('Please build a formula first');
            return;
        }

        const result = arithmeticEngine.saveFormula(name, formula);
        if (!result.success) {
            alert(result.error);
            return;
        }

        // Clear and refresh
        document.getElementById('formula-name-new').value = '';
        clearFormulaDisplay();
        renderFormulasListNew();
    });
}

function addStreamToFormula(streamName) {
    arithmeticEngine.addToken('stream', streamName);
    updateFormulaDisplay();
}

function addOperatorToFormula(operator) {
    arithmeticEngine.addToken('operator', operator);
    updateFormulaDisplay();
}

function clearFormulaDisplay() {
    arithmeticEngine.clearFormula();
    updateFormulaDisplay();
}

function updateFormulaDisplay() {
    const display = document.getElementById('formula-display');
    const preview = document.getElementById('formula-preview-new');
    const previewText = document.getElementById('formula-preview-text-new');

    const formula = arithmeticEngine.buildFormulaString();

    if (!formula) {
        display.innerHTML = '<span class="placeholder-text">Drag streams here or use buttons below</span>';
        preview.style.display = 'none';
        return;
    }

    // Display formula with visual formatting
    display.innerHTML = arithmeticEngine.currentFormula.map(token => {
        if (token.type === 'stream') {
            return `<span class="stream-chip">${escapeHtml(token.value)}</span>`;
        }
        return `<span class="operator">${escapeHtml(token.value)}</span>`;
    }).join('');

    // Show preview
    const result = arithmeticEngine.evaluateFormula(formula);
    if (result.error) {
        preview.className = 'formula-preview error';
        previewText.textContent = result.error;
        preview.style.display = 'block';
    } else if (result.cashflows) {
        const total = result.cashflows.reduce((a, b) => a + b, 0);
        const avg = total / result.cashflows.length;
        preview.className = 'formula-preview success';
        previewText.textContent = `Total: $${total.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})} | Avg/Month: $${avg.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}`;
        preview.style.display = 'block';
    }
}

function renderFormulasListNew() {
    const container = document.getElementById('formulas-list-new');
    const formulas = arithmeticEngine.getFormulas();

    if (formulas.length === 0) {
        container.innerHTML = '<p class="help-text">No formulas saved yet</p>';
        return;
    }

    container.innerHTML = '';
    for (const formula of formulas) {
        const item = document.createElement('div');
        item.className = 'formula-item';

        // Calculate summary stats
        let statsHTML = '';
        if (formula.cashflows && formula.cashflows.length > 0) {
            const total = formula.cashflows.reduce((a, b) => a + b, 0);
            const avg = total / formula.cashflows.length;
            const max = Math.max(...formula.cashflows);
            const min = Math.min(...formula.cashflows);
            statsHTML = `
                <div class="result-stats">
                    <span>Total: $${total.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                    <span>Avg/Month: $${avg.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                    <span>Max: $${max.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                    <span>Min: $${min.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                </div>
            `;
        }

        // Create unique canvas ID
        const canvasId = `chart-formula-${formula.name.replace(/[^a-zA-Z0-9]/g, '_')}`;

        item.innerHTML = `
            <div class="formula-item-header">
                <div class="formula-item-content">
                    <div class="formula-item-name">${escapeHtml(formula.name)}</div>
                    <div class="formula-item-expression">${escapeHtml(formula.formula)}</div>
                </div>
                <button class="btn btn-sm" onclick="removeFormulaNew('${escapeHtml(formula.name)}')">Remove</button>
            </div>
            ${statsHTML}
            ${formula.cashflows ? `<div class="formula-item-chart-container"><canvas id="${canvasId}" class="formula-item-chart"></canvas></div>` : ''}
        `;
        container.appendChild(item);

        // Render chart if we have cashflows
        if (formula.cashflows && formula.cashflows.length > 0) {
            setTimeout(() => renderFormulaChart(canvasId, formula.name, formula.cashflows), 0);
        }
    }
}

function renderFormulaChart(canvasId, label, cashflows) {
    const canvas = document.getElementById(canvasId);
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    new Chart(ctx, {
        type: 'line',
        data: {
            labels: cashflows.map((_, i) => `M${i}`),
            datasets: [{
                label: label,
                data: cashflows,
                borderColor: '#2196F3',
                backgroundColor: 'rgba(33, 150, 243, 0.1)',
                tension: 0.1,
                fill: true,
                pointRadius: 2,
                pointHoverRadius: 4
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {display: false},
                title: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: (context) => {
                            const value = context.parsed.y;
                            return label + ': $' + value.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0});
                        }
                    }
                }
            },
            scales: {
                x: {
                    grid: {
                        display: false
                    },
                    ticks: {
                        maxRotation: 0,
                        autoSkipPadding: 20
                    }
                },
                y: {
                    ticks: {
                        callback: (value) => '$' + value.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})
                    },
                    grid: {
                        color: '#f0f0f0'
                    }
                }
            }
        }
    });
}

function removeFormulaNew(name) {
    if (confirm(`Remove formula "${name}"?`)) {
        arithmeticEngine.removeFormula(name);
        renderFormulasListNew();
    }
}

// Hook into calculation results
function updateArithmeticEngine(results) {
    if (results && results.stream_details) {
        // Get model reference (could be session.model or currentModel)
        const model = (typeof session !== 'undefined' && session.model) ? session.model : currentModel;

        if (!model || !model.streams) {
            console.error('No model available for arithmetic engine');
            return;
        }

        // Convert stream_details object to array format
        const detailsArray = Object.entries(results.stream_details).map(([id, cashflows]) => {
            // Access stream directly by ID (streams is an object/dict, not array)
            let stream;
            if (Array.isArray(model.streams)) {
                stream = model.streams.find(s => s.id === id);
            } else {
                stream = model.streams[id];
            }

            return {
                stream_name: stream ? stream.name : id,
                stream_type: stream ? stream.stream_type : 'REVENUE',
                cashflows: cashflows
            };
        });

        arithmeticEngine.setStreamDetails(detailsArray);
        renderAvailableStreams();

        // Recalculate existing formulas
        arithmeticEngine.recalculateAll();
        renderFormulasListNew();
    }
}

// Sync formulas to backend
async function syncFormulasToBackend() {
    const formulas = arithmeticEngine.exportFormulas();
    try {
        await fetch('http://localhost:8989/model/formulas', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(formulas)
        });
    } catch (error) {
        console.error('Failed to sync formulas to backend:', error);
    }
}

// Load formulas from model
function loadFormulasFromModel(model) {
    if (model && model.arithmetic_formulas) {
        arithmeticEngine.loadFormulas(model.arithmetic_formulas);
        renderFormulasListNew();
    } else {
        arithmeticEngine.clearFormulas();
        renderFormulasListNew();
    }
}

// Helper function for HTML escaping
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return unsafe;
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

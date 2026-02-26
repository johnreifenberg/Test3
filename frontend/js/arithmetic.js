/**
 * Streams Arithmetic Engine
 * Evaluates formulas on stream cashflows from last calculation results.
 */

class ArithmeticEngine {
    constructor() {
        this.formulas = [];  // [{name, formula, cashflows}]
        this.streamDetails = null;  // From last calculation
    }

    setStreamDetails(details) {
        this.streamDetails = details;
    }

    parseFormula(formula) {
        /**
         * Tokenize formula string into stream names, operators, and parentheses.
         * Stream names can contain letters, numbers, underscores.
         * Returns: {valid: bool, tokens: [], error: string}
         */
        const tokens = [];
        const pattern = /([a-zA-Z_][a-zA-Z0-9_]*)|([+\-*/()])/g;
        let match;

        while ((match = pattern.exec(formula)) !== null) {
            tokens.push(match[0]);
        }

        return {valid: true, tokens, error: null};
    }

    validateFormula(formula) {
        /**
         * Check if formula is syntactically valid and all streams exist.
         * Returns: {valid: bool, error: string}
         */
        if (!this.streamDetails) {
            return {valid: false, error: "No calculation results available. Run a calculation first."};
        }

        const parsed = this.parseFormula(formula);
        if (!parsed.valid) {
            return {valid: false, error: parsed.error};
        }

        // Check all stream references exist
        const streamNames = new Set(this.streamDetails.map(s => s.stream_name));
        for (const token of parsed.tokens) {
            if (/^[a-zA-Z_]/.test(token)) {
                // It's a stream name
                if (!streamNames.has(token)) {
                    return {valid: false, error: `Stream "${token}" not found in model`};
                }
            }
        }

        return {valid: true, error: null};
    }

    evaluateFormula(formula) {
        /**
         * Evaluate formula month-by-month using stream cashflows.
         * Returns: {cashflows: number[], error: string}
         */
        const validation = this.validateFormula(formula);
        if (!validation.valid) {
            return {cashflows: null, error: validation.error};
        }

        // Build lookup: stream_name -> cashflows array
        const streamCashflows = {};
        for (const detail of this.streamDetails) {
            streamCashflows[detail.stream_name] = detail.cashflows;
        }

        // Determine result length (max of all referenced streams)
        let maxLength = 0;
        const parsed = this.parseFormula(formula);
        for (const token of parsed.tokens) {
            if (streamCashflows[token]) {
                maxLength = Math.max(maxLength, streamCashflows[token].length);
            }
        }

        // Evaluate month by month
        const result = new Array(maxLength).fill(0);
        for (let month = 0; month < maxLength; month++) {
            // Build expression with values for this month
            let expr = formula;
            for (const [name, cfs] of Object.entries(streamCashflows)) {
                const value = month < cfs.length ? cfs[month] : 0;
                // Replace stream name with value (use regex with word boundaries)
                expr = expr.replace(new RegExp('\\b' + name + '\\b', 'g'), value);
            }

            try {
                // Evaluate using Function constructor (safer than eval)
                result[month] = new Function('return ' + expr)();
            } catch (e) {
                return {cashflows: null, error: `Evaluation error at month ${month}: ${e.message}`};
            }
        }

        return {cashflows: result, error: null};
    }

    addFormula(name, formula) {
        const result = this.evaluateFormula(formula);
        if (result.error) {
            return {success: false, error: result.error};
        }

        // Check for duplicate names
        if (this.formulas.find(f => f.name === name)) {
            return {success: false, error: `Formula "${name}" already exists`};
        }

        this.formulas.push({name, formula, cashflows: result.cashflows});
        syncFormulasToBackend();  // Persist to backend
        return {success: true};
    }

    removeFormula(name) {
        this.formulas = this.formulas.filter(f => f.name !== name);
        syncFormulasToBackend();  // Persist to backend
    }

    getFormulas() {
        return this.formulas;
    }

    clearFormulas() {
        this.formulas = [];
    }

    loadFormulas(formulas) {
        /**
         * Load formulas from saved model data.
         * Formulas are stored as [{name, formula}] without cashflows.
         * Cashflows will be recalculated when results are available.
         */
        this.formulas = [];
        if (!formulas || !Array.isArray(formulas)) {
            return;
        }
        for (const f of formulas) {
            if (f.name && f.formula) {
                // Don't evaluate yet - wait for calculation results
                this.formulas.push({
                    name: f.name,
                    formula: f.formula,
                    cashflows: null  // Will be calculated later
                });
            }
        }
    }

    exportFormulas() {
        /**
         * Export formulas for saving to model JSON.
         * Only save name and formula, not cashflows (they're derived).
         */
        return this.formulas.map(f => ({
            name: f.name,
            formula: f.formula
        }));
    }

    recalculateAll() {
        /**
         * Recalculate all formulas using current stream details.
         * Call this after loading formulas or after new calculation results.
         */
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
    const formulaInput = document.getElementById('formula-input');
    const formulaName = document.getElementById('formula-name');
    const btnAdd = document.getElementById('btn-add-formula');
    const btnClear = document.getElementById('btn-clear-formula');

    // Populate stream buttons
    updateStreamButtons();

    // Real-time formula preview with debouncing
    let previewTimeout = null;
    formulaInput.addEventListener('input', () => {
        clearTimeout(previewTimeout);
        previewTimeout = setTimeout(() => {
            updateFormulaPreview(formulaInput.value.trim());
        }, 300);  // 300ms debounce
    });

    btnAdd.addEventListener('click', () => {
        const name = formulaName.value.trim();
        const formula = formulaInput.value.trim();

        if (!name || !formula) {
            alert('Please enter both a name and formula');
            return;
        }

        const result = arithmeticEngine.addFormula(name, formula);
        if (!result.success) {
            alert(result.error);
            return;
        }

        formulaName.value = '';
        formulaInput.value = '';
        hideFormulaPreview();
        renderFormulasList();
        renderArithmeticResults();
    });

    btnClear.addEventListener('click', () => {
        formulaName.value = '';
        formulaInput.value = '';
        hideFormulaPreview();
    });
}

function updateFormulaPreview(formula) {
    const previewDiv = document.getElementById('formula-preview');
    const previewText = document.getElementById('formula-preview-text');

    if (!formula) {
        hideFormulaPreview();
        return;
    }

    const result = arithmeticEngine.evaluateFormula(formula);

    if (result.error) {
        previewDiv.className = 'formula-preview error';
        previewText.textContent = result.error;
        previewDiv.style.display = 'block';
    } else if (result.cashflows) {
        const total = result.cashflows.reduce((a, b) => a + b, 0);
        const avg = total / result.cashflows.length;
        previewDiv.className = 'formula-preview success';
        previewText.textContent = `Total: $${total.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})} | Avg/Month: $${avg.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}`;
        previewDiv.style.display = 'block';
    } else {
        hideFormulaPreview();
    }
}

function hideFormulaPreview() {
    const previewDiv = document.getElementById('formula-preview');
    previewDiv.style.display = 'none';
}

function updateStreamButtons() {
    const container = document.getElementById('stream-buttons');
    if (!session.model || !session.model.streams) {
        container.innerHTML = '<p class="help-text">No streams available</p>';
        return;
    }

    container.innerHTML = '';
    const streams = Array.isArray(session.model.streams) ? session.model.streams : Object.values(session.model.streams);
    for (const stream of streams) {
        const btn = document.createElement('button');
        btn.className = 'stream-button';
        btn.textContent = stream.name;
        btn.type = 'button';  // Prevent form submission
        btn.addEventListener('click', (e) => {
            e.preventDefault();
            const input = document.getElementById('formula-input');
            input.value += stream.name;
            input.focus();
        });
        container.appendChild(btn);
    }
}

function renderFormulasList() {
    const container = document.getElementById('formulas-list');
    const formulas = arithmeticEngine.getFormulas();

    if (formulas.length === 0) {
        container.innerHTML = '<p class="help-text">No formulas saved yet</p>';
        return;
    }

    container.innerHTML = '';
    for (const formula of formulas) {
        const item = document.createElement('div');
        item.className = 'formula-item';
        item.innerHTML = `
            <div>
                <strong>${escapeHtml(formula.name)}</strong>
                <span class="formula-text"> = ${escapeHtml(formula.formula)}</span>
            </div>
            <button class="btn btn-sm" onclick="removeFormula('${escapeHtml(formula.name)}')">Remove</button>
        `;
        container.appendChild(item);
    }
}

function removeFormula(name) {
    arithmeticEngine.removeFormula(name);
    renderFormulasList();
    renderArithmeticResults();
}

function renderArithmeticResults() {
    const container = document.getElementById('arithmetic-results');
    const formulas = arithmeticEngine.getFormulas();

    if (formulas.length === 0) {
        container.innerHTML = '<p class="placeholder">Add a formula to see results</p>';
        return;
    }

    // Render each formula as a chart and summary
    container.innerHTML = '<h3>Results</h3>';
    for (const formula of formulas) {
        const section = document.createElement('div');
        section.className = 'formula-result-section';

        // Calculate summary stats
        const total = formula.cashflows.reduce((a, b) => a + b, 0);
        const avg = total / formula.cashflows.length;
        const max = Math.max(...formula.cashflows);
        const min = Math.min(...formula.cashflows);

        const canvasId = `chart-${formula.name.replace(/[^a-zA-Z0-9]/g, '_')}`;
        section.innerHTML = `
            <h4>${escapeHtml(formula.name)}</h4>
            <div class="result-stats">
                <span>Total: $${total.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                <span>Avg/Month: $${avg.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                <span>Max: $${max.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
                <span>Min: $${min.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})}</span>
            </div>
            <canvas id="${canvasId}" width="800" height="300"></canvas>
        `;
        container.appendChild(section);

        // Render chart
        renderArithmeticChart(canvasId, formula.name, formula.cashflows);
    }
}

function renderArithmeticChart(canvasId, label, cashflows) {
    const ctx = document.getElementById(canvasId).getContext('2d');
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
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                title: {display: true, text: label},
                legend: {display: false}
            },
            scales: {
                y: {
                    ticks: {
                        callback: (value) => '$' + value.toLocaleString('en-US', {minimumFractionDigits: 0, maximumFractionDigits: 0})
                    }
                }
            }
        }
    });
}

// Hook into calculation results
function updateArithmeticEngine(results) {
    if (results && results.stream_details) {
        arithmeticEngine.setStreamDetails(results.stream_details);
        updateStreamButtons();
        // Recalculate existing formulas with new stream data
        arithmeticEngine.recalculateAll();
        renderFormulasList();
        renderArithmeticResults();
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
        renderFormulasList();
        renderArithmeticResults();
    } else {
        arithmeticEngine.clearFormulas();
        renderFormulasList();
        renderArithmeticResults();
    }
}

// Helper function for HTML escaping (if not already available)
function escapeHtml(unsafe) {
    if (typeof unsafe !== 'string') return unsafe;
    return unsafe
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}

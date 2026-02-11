/* ── Global State ──────────────────────────────────────────────── */
let currentModel = null;

/* ── Initialization ────────────────────────────────────────────── */
async function init() {
    setupEventListeners();
    setupModelBuilderEvents();
    await loadModel();
}

function setupEventListeners() {
    // Header buttons
    document.getElementById('btn-new').addEventListener('click', createNewModel);
    document.getElementById('btn-load').addEventListener('click', loadModelFromFile);
    document.getElementById('btn-save').addEventListener('click', saveModelToFile);
    document.getElementById('btn-template').addEventListener('click', showTemplateSelector);

    // Stream management
    document.getElementById('btn-add-stream').addEventListener('click', () => showStreamModal());

    // Calculation buttons
    document.getElementById('btn-run-deterministic').addEventListener('click', runDeterministic);
    document.getElementById('btn-run-monte-carlo').addEventListener('click', runMonteCarlo);
    document.getElementById('btn-run-sensitivity').addEventListener('click', runSensitivity);
    document.getElementById('btn-load-breakeven-params').addEventListener('click', loadBreakevenParams);
    document.getElementById('btn-run-breakeven').addEventListener('click', runBreakeven);
    document.getElementById('btn-export-excel').addEventListener('click', exportExcel);
    document.getElementById('btn-export-pdf').addEventListener('click', exportPDF);

    // Tab switching
    document.querySelectorAll('.tab').forEach(tab => {
        tab.addEventListener('click', () => switchTab(tab.dataset.tab));
    });

    // Template modal close
    document.getElementById('close-template-modal').addEventListener('click', () => {
        document.getElementById('modal-template').classList.remove('active');
    });
}

/* ── Model Operations ──────────────────────────────────────────── */
async function loadModel() {
    try {
        const data = await api.get('/model');
        if (data && data.name) {
            currentModel = data;
            renderModel();
        }
    } catch (e) {
        console.log('No model loaded yet.');
    }
}

function renderModel() {
    if (!currentModel) return;
    renderStreamList(currentModel);
    renderCashflowsTab(currentModel);

    // Update settings form
    if (currentModel.settings) {
        document.getElementById('model-name').value = currentModel.name || '';
        document.getElementById('forecast-months').value = currentModel.settings.forecast_months || 60;
        document.getElementById('terminal-growth').value = currentModel.settings.terminal_growth_rate || 0.025;

        // Calculation mode
        const calcMode = currentModel.settings.calculation_mode || 'NPV';
        document.getElementById('calculation-mode').value = calcMode;
        toggleCalculationMode();

        if (currentModel.settings.discount_rate) {
            const dr = currentModel.settings.discount_rate;
            document.getElementById('dr-dist-type').value = dr.type;
            renderDistParams('dr-params', dr.type, 'dr', dr.params);
        }

        // Escalation rate
        const esc = currentModel.settings.escalation_rate;
        if (esc) {
            document.getElementById('has-escalation').checked = true;
            document.getElementById('escalation-section').style.display = 'block';
            document.getElementById('esc-dist-type').value = esc.type;
            renderDistParams('esc-params', esc.type, 'esc', esc.params);
        } else {
            document.getElementById('has-escalation').checked = false;
            document.getElementById('escalation-section').style.display = 'none';
        }
    }
}

async function createNewModel() {
    const name = prompt('Model name:', 'New DCF Model');
    if (!name) return;

    const drDist = getDistFromInputs('dr-dist-type', 'dr-params');
    let escDist = null;
    if (document.getElementById('has-escalation').checked) {
        escDist = getDistFromInputs('esc-dist-type', 'esc-params');
    }

    try {
        currentModel = await api.post('/model/new', {
            name: name,
            forecast_months: parseInt(document.getElementById('forecast-months').value) || 60,
            terminal_growth_rate: parseFloat(document.getElementById('terminal-growth').value) || 0.025,
            discount_rate: drDist || { type: 'NORMAL', params: { mean: 0.12, std: 0.02 } },
            escalation_rate: escDist,
            calculation_mode: document.getElementById('calculation-mode').value || 'NPV',
        });
        renderModel();
        showStatus('New model created.');
    } catch (e) {
        alert('Error creating model: ' + e.message);
    }
}

async function loadModelFromFile() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
            currentModel = await api.uploadFile('/model/load', file);
            renderModel();
            showStatus('Model loaded successfully.');
        } catch (e) {
            alert('Error loading model: ' + e.message);
        }
    };
    input.click();
}

async function saveModelToFile() {
    if (!currentModel) { alert('No model to save.'); return; }
    try {
        await api.downloadFile('/model/save', `${(currentModel.name || 'model').replace(/\s+/g, '_')}.json`);
        showStatus('Model saved.');
    } catch (e) {
        alert('Error saving model: ' + e.message);
    }
}

async function showTemplateSelector() {
    try {
        const templates = await api.get('/model/templates');
        const container = document.getElementById('template-list');
        container.innerHTML = '';

        const names = Object.keys(templates);
        if (names.length === 0) {
            container.innerHTML = '<p class="text-muted">No templates available.</p>';
        } else {
            names.forEach(name => {
                const tpl = templates[name];
                const div = document.createElement('div');
                div.className = 'template-item';
                const streamCount = tpl.streams ? (Array.isArray(tpl.streams) ? tpl.streams.length : Object.keys(tpl.streams).length) : 0;
                div.innerHTML = `
                    <div class="template-name">${tpl.name || name}</div>
                    <div class="template-desc">${streamCount} streams, ${tpl.settings.forecast_months} months</div>
                `;
                div.addEventListener('click', async () => {
                    try {
                        currentModel = await api.post(`/model/template/${name}`);
                        renderModel();
                        document.getElementById('modal-template').classList.remove('active');
                        showStatus(`Template "${tpl.name || name}" loaded.`);
                    } catch (e) {
                        alert('Error loading template: ' + e.message);
                    }
                });
                container.appendChild(div);
            });
        }

        document.getElementById('modal-template').classList.add('active');
    } catch (e) {
        alert('Error fetching templates: ' + e.message);
    }
}

/* ── Settings Update ───────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', () => {
    const btn = document.getElementById('btn-update-settings');
    if (btn) {
        btn.addEventListener('click', async () => {
            if (!currentModel) {
                alert('Create or load a model first.');
                return;
            }
            const drDist = getDistFromInputs('dr-dist-type', 'dr-params');
            let escDist = null;
            if (document.getElementById('has-escalation').checked) {
                escDist = getDistFromInputs('esc-dist-type', 'esc-params');
            }
            try {
                currentModel = await api.put('/model/settings', {
                    name: document.getElementById('model-name').value || 'Untitled Model',
                    forecast_months: parseInt(document.getElementById('forecast-months').value) || 60,
                    terminal_growth_rate: parseFloat(document.getElementById('terminal-growth').value) || 0.025,
                    discount_rate: drDist || { type: 'NORMAL', params: { mean: 0.12, std: 0.02 } },
                    escalation_rate: escDist,
                    calculation_mode: document.getElementById('calculation-mode').value || 'NPV',
                });
                renderModel();
                showStatus('Settings updated.');
            } catch (e) {
                alert('Error updating settings: ' + e.message);
            }
        });
    }
});

/* ── Calculations ──────────────────────────────────────────────── */
async function runDeterministic() {
    if (!currentModel) { alert('No model loaded.'); return; }
    showStatus('Running deterministic calculation...');
    try {
        const results = await api.post('/calculate/deterministic');
        displayDeterministicResults(results);
        showStatus('Deterministic calculation complete.');
    } catch (e) {
        showStatus('Error: ' + e.message);
    }
}

async function runMonteCarlo() {
    if (!currentModel) { alert('No model loaded.'); return; }
    const nSim = parseInt(document.getElementById('n-simulations').value) || 10000;
    showStatus(`Running Monte Carlo (${nSim.toLocaleString()} simulations)...`);
    try {
        const results = await api.post('/calculate/monte-carlo', { n_simulations: nSim });
        displayMonteCarloResults(results);
        showStatus('Monte Carlo simulation complete.');
    } catch (e) {
        showStatus('Error: ' + e.message);
    }
}

async function runSensitivity() {
    if (!currentModel) { alert('No model loaded.'); return; }
    showStatus('Running sensitivity analysis...');
    try {
        const results = await api.post('/calculate/sensitivity');
        displaySensitivityResults(results);
        showStatus('Sensitivity analysis complete.');
    } catch (e) {
        showStatus('Error: ' + e.message);
    }
}

/* ── Display Results ───────────────────────────────────────────── */
function formatCurrency(val) {
    if (val === null || val === undefined) return 'N/A';
    return '$' + val.toLocaleString(undefined, { minimumFractionDigits: 0, maximumFractionDigits: 0 });
}

function formatPercent(val) {
    if (val === null || val === undefined) return 'N/A';
    return (val * 100).toFixed(2) + '%';
}

function displayDeterministicResults(results) {
    switchTab('results');
    const container = document.getElementById('results-container');
    const isIRR = results.calculation_mode === 'IRR';

    let cardsHTML;
    if (isIRR) {
        const irrDisplay = results.irr !== null ? formatPercent(results.irr) : (results.irr_error || 'N/A');
        cardsHTML = `
            <div class="result-card">
                <div class="label">Internal Rate of Return</div>
                <div class="value">${irrDisplay}</div>
            </div>
        `;
        if (results.irr_error && results.irr === null) {
            cardsHTML += `
                <div class="result-card">
                    <div class="label">Error</div>
                    <div class="value" style="font-size:0.85rem;">${results.irr_error}</div>
                </div>
            `;
        }
    } else {
        const paybackDisplay = results.payback_period !== null && results.payback_period !== undefined
            ? results.payback_period.toFixed(1) + ' months' : 'Never';
        cardsHTML = `
            <div class="result-card">
                <div class="label">Net Present Value</div>
                <div class="value">${formatCurrency(results.npv)}</div>
            </div>
            <div class="result-card">
                <div class="label">Internal Rate of Return</div>
                <div class="value">${results.irr !== null ? formatPercent(results.irr) : 'N/A'}</div>
            </div>
            <div class="result-card">
                <div class="label">Terminal Value (PV)</div>
                <div class="value">${formatCurrency(results.terminal_value)}</div>
            </div>
            <div class="result-card">
                <div class="label">Discount Rate</div>
                <div class="value">${formatPercent(results.discount_rate)}</div>
            </div>
            <div class="result-card">
                <div class="label">Payback Period</div>
                <div class="value">${paybackDisplay}</div>
            </div>
        `;
    }

    container.innerHTML = `
        <h3>Deterministic Results${isIRR ? ' (IRR Mode)' : ''}</h3>
        <div class="results-grid">
            ${cardsHTML}
        </div>
        <div class="chart-container">
            <h3>Monthly Cashflows</h3>
            <canvas id="cashflow-chart" height="300"></canvas>
        </div>
    `;

    chartManager.renderCashflowChart('cashflow-chart', results.cashflows);
    document.getElementById('btn-export-excel').style.display = 'inline-block';
    document.getElementById('btn-export-pdf').style.display = 'inline-block';
}

function displayMonteCarloResults(results) {
    switchTab('results');
    const container = document.getElementById('results-container');
    const isIRR = results.calculation_mode === 'IRR';

    let cardsHTML;
    let chartTitle;
    let distData;

    if (isIRR) {
        const fmt = formatPercent;
        cardsHTML = `
            <div class="result-card">
                <div class="label">IRR Mean</div>
                <div class="value">${fmt(results.irr_mean)}</div>
            </div>
            <div class="result-card">
                <div class="label">IRR Median</div>
                <div class="value">${fmt(results.irr_median)}</div>
            </div>
            <div class="result-card">
                <div class="label">IRR Std Dev</div>
                <div class="value">${fmt(results.irr_std)}</div>
            </div>
            <div class="result-card">
                <div class="label">P10</div>
                <div class="value">${fmt(results.irr_p10)}</div>
            </div>
            <div class="result-card">
                <div class="label">P90</div>
                <div class="value">${fmt(results.irr_p90)}</div>
            </div>
        `;
        if (results.irr_failed_count > 0) {
            cardsHTML += `
                <div class="result-card">
                    <div class="label">Failed Simulations</div>
                    <div class="value">${results.irr_failed_count}</div>
                </div>
            `;
        }
        chartTitle = 'IRR Distribution';
        distData = results.irr_distribution || [];
    } else {
        const formatPayback = (v) => v !== null && v !== undefined ? v.toFixed(1) + ' mo' : 'N/A';
        let paybackCards = '';
        if (results.payback_mean !== null && results.payback_mean !== undefined) {
            paybackCards = `
                <div class="result-card">
                    <div class="label">Payback Mean</div>
                    <div class="value">${formatPayback(results.payback_mean)}</div>
                </div>
                <div class="result-card">
                    <div class="label">Payback Median</div>
                    <div class="value">${formatPayback(results.payback_median)}</div>
                </div>
                <div class="result-card">
                    <div class="label">Payback P10</div>
                    <div class="value">${formatPayback(results.payback_p10)}</div>
                </div>
                <div class="result-card">
                    <div class="label">Payback P90</div>
                    <div class="value">${formatPayback(results.payback_p90)}</div>
                </div>
            `;
        }
        if (results.payback_never_count > 0) {
            paybackCards += `
                <div class="result-card">
                    <div class="label">Never Pays Back</div>
                    <div class="value">${results.payback_never_count}</div>
                </div>
            `;
        }
        cardsHTML = `
            <div class="result-card">
                <div class="label">NPV Mean</div>
                <div class="value">${formatCurrency(results.npv_mean)}</div>
            </div>
            <div class="result-card">
                <div class="label">NPV Median</div>
                <div class="value">${formatCurrency(results.npv_median)}</div>
            </div>
            <div class="result-card">
                <div class="label">NPV Std Dev</div>
                <div class="value">${formatCurrency(results.npv_std)}</div>
            </div>
            <div class="result-card">
                <div class="label">P10</div>
                <div class="value">${formatCurrency(results.npv_p10)}</div>
            </div>
            <div class="result-card">
                <div class="label">P25</div>
                <div class="value">${formatCurrency(results.npv_p25)}</div>
            </div>
            <div class="result-card">
                <div class="label">P75</div>
                <div class="value">${formatCurrency(results.npv_p75)}</div>
            </div>
            <div class="result-card">
                <div class="label">P90</div>
                <div class="value">${formatCurrency(results.npv_p90)}</div>
            </div>
            ${paybackCards}
        `;
        chartTitle = 'NPV Distribution';
        distData = results.npv_distribution || [];
    }

    container.innerHTML = `
        <h3>Monte Carlo Results (${results.n_simulations.toLocaleString()} simulations)${isIRR ? ' - IRR Mode' : ''}</h3>
        <div class="results-grid">
            ${cardsHTML}
        </div>
        <div class="chart-container">
            <h3>${chartTitle}</h3>
            <canvas id="npv-distribution" height="300"></canvas>
        </div>
    `;

    if (distData.length > 0) {
        chartManager.renderNPVDistribution('npv-distribution', distData, isIRR ? 'IRR (%)' : undefined);
    }
    document.getElementById('btn-export-excel').style.display = 'inline-block';
    document.getElementById('btn-export-pdf').style.display = 'inline-block';
}

function displaySensitivityResults(results) {
    switchTab('results');
    const container = document.getElementById('results-container');

    if (!results.parameters || results.parameters.length === 0) {
        container.innerHTML = `
            <h3>Sensitivity Analysis</h3>
            <p>No uncertain parameters found. Add non-FIXED distributions to see sensitivity results.</p>
        `;
        return;
    }

    let tableHTML = `
        <table style="width:100%; border-collapse:collapse; margin-top:12px;">
            <tr style="border-bottom:2px solid var(--border);">
                <th style="text-align:left; padding:8px;">Parameter</th>
                <th style="text-align:right; padding:8px;">NPV Low</th>
                <th style="text-align:right; padding:8px;">NPV High</th>
                <th style="text-align:right; padding:8px;">Swing</th>
            </tr>
    `;
    results.parameters.forEach(p => {
        tableHTML += `
            <tr style="border-bottom:1px solid var(--border);">
                <td style="padding:8px;">${p.parameter_name}</td>
                <td style="text-align:right; padding:8px;">${formatCurrency(p.npv_low)}</td>
                <td style="text-align:right; padding:8px;">${formatCurrency(p.npv_high)}</td>
                <td style="text-align:right; padding:8px; font-weight:600;">${formatCurrency(p.swing)}</td>
            </tr>
        `;
    });
    tableHTML += '</table>';

    container.innerHTML = `
        <h3>Sensitivity Analysis</h3>
        <p class="text-muted">Baseline NPV: ${formatCurrency(results.baseline_npv)}</p>
        <div class="chart-container">
            <h3>Tornado Chart - Key Value Drivers</h3>
            <canvas id="tornado-chart" height="${Math.max(200, results.parameters.length * 35)}"></canvas>
        </div>
        ${tableHTML}
    `;

    chartManager.renderTornadoChart('tornado-chart', results.parameters);
}

/* ── Breakeven Analysis ────────────────────────────────────────── */
let breakevenParams = [];

async function loadBreakevenParams() {
    if (!currentModel) { alert('No model loaded.'); return; }
    try {
        breakevenParams = await api.get('/calculate/breakeven/parameters');
        const select = document.getElementById('breakeven-param');
        select.innerHTML = '';
        if (breakevenParams.length === 0) {
            select.innerHTML = '<option value="">No solvable parameters</option>';
            return;
        }
        breakevenParams.forEach((p, i) => {
            const opt = document.createElement('option');
            opt.value = i;
            opt.textContent = p.parameter_name;
            select.appendChild(opt);
        });
        showStatus(`Loaded ${breakevenParams.length} breakeven parameters.`);
    } catch (e) {
        showStatus('Error loading parameters: ' + e.message);
    }
}

async function runBreakeven() {
    if (!currentModel) { alert('No model loaded.'); return; }
    const select = document.getElementById('breakeven-param');
    const idx = parseInt(select.value);
    if (isNaN(idx) || !breakevenParams[idx]) {
        alert('Select a parameter first. Click "Load Parameters".');
        return;
    }
    const param = breakevenParams[idx];
    const targetNpv = parseFloat(document.getElementById('breakeven-target').value) || 0;
    showStatus('Running breakeven analysis...');
    try {
        const result = await api.post('/calculate/breakeven', {
            stream_id: param.stream_id,
            parameter_name: param.parameter_name,
            target_npv: targetNpv,
        });
        const container = document.getElementById('breakeven-result');
        if (result.found) {
            const isPercent = param.parameter_name === 'Discount Rate' || param.parameter_name === 'Escalation Rate';
            const fmtVal = isPercent ? formatPercent(result.breakeven_value) : formatCurrency(result.breakeven_value);
            const fmtOrig = isPercent ? formatPercent(result.original_value) : formatCurrency(result.original_value);
            container.innerHTML = `
                <div class="result-card" style="margin-top:8px;">
                    <div class="label">Breakeven: ${param.parameter_name}</div>
                    <div class="value">${fmtVal}</div>
                    <div class="label" style="margin-top:4px;">Current value: ${fmtOrig} | Target NPV: ${formatCurrency(targetNpv)}</div>
                </div>
            `;
        } else {
            container.innerHTML = `<p style="color:var(--danger);">${result.error || 'No breakeven found.'}</p>`;
        }
        showStatus('Breakeven analysis complete.');
    } catch (e) {
        showStatus('Error: ' + e.message);
    }
}

/* ── Export ─────────────────────────────────────────────────────── */
async function exportExcel() {
    try {
        await api.downloadFile('/export/excel', 'dcf_results.xlsx');
        showStatus('Excel exported.');
    } catch (e) {
        alert('Error exporting: ' + e.message);
    }
}

async function exportPDF() {
    const container = document.getElementById('results-container');
    if (!container || container.querySelector('.placeholder')) {
        alert('No results to export. Run a calculation first.');
        return;
    }
    showStatus('Generating PDF...');
    try {
        const { jsPDF } = window.jspdf;
        const pdf = new jsPDF({ orientation: 'landscape', unit: 'mm', format: 'a4' });
        const pageW = pdf.internal.pageSize.getWidth();
        const pageH = pdf.internal.pageSize.getHeight();
        const margin = 15;

        // Title
        pdf.setFontSize(20);
        pdf.text(currentModel ? currentModel.name : 'DCF Report', margin, 20);

        // Date and settings summary
        pdf.setFontSize(10);
        pdf.setTextColor(100);
        const dateStr = new Date().toLocaleDateString();
        pdf.text(`Generated: ${dateStr}`, margin, 28);
        if (currentModel && currentModel.settings) {
            const s = currentModel.settings;
            pdf.text(`Forecast: ${s.forecast_months} months | Mode: ${s.calculation_mode || 'NPV'}`, margin, 34);
        }
        pdf.setTextColor(0);

        // Capture results container
        const canvas = await html2canvas(container, {
            scale: 2,
            useCORS: true,
            backgroundColor: '#ffffff',
        });
        const imgData = canvas.toDataURL('image/png');
        const imgW = pageW - margin * 2;
        const imgH = (canvas.height / canvas.width) * imgW;

        let yPos = 40;
        if (imgH <= pageH - yPos - margin) {
            pdf.addImage(imgData, 'PNG', margin, yPos, imgW, imgH);
        } else {
            // Scale to fit page height if needed
            const fitH = pageH - yPos - margin;
            const fitW = (canvas.width / canvas.height) * fitH;
            pdf.addImage(imgData, 'PNG', margin, yPos, Math.min(fitW, imgW), fitH);
        }

        const modelName = (currentModel ? currentModel.name : 'report').replace(/\s+/g, '_');
        pdf.save(`${modelName}_report.pdf`);
        showStatus('PDF exported.');
    } catch (e) {
        showStatus('PDF export error: ' + e.message);
        console.error('PDF export error:', e);
    }
}

/* ── Tab Switching ─────────────────────────────────────────────── */
function switchTab(tabName) {
    document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.remove('active'));
    const tabBtn = document.querySelector(`.tab[data-tab="${tabName}"]`);
    const tabContent = document.getElementById(`tab-${tabName}`);
    if (tabBtn) tabBtn.classList.add('active');
    if (tabContent) tabContent.classList.add('active');
}

/* ── Status Bar ────────────────────────────────────────────────── */
function showStatus(message) {
    const el = document.getElementById('calculation-status');
    if (el) el.textContent = message;
}

/* ── Boot ──────────────────────────────────────────────────────── */
document.addEventListener('DOMContentLoaded', init);

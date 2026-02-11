class ChartManager {
    constructor() {
        this.charts = {};
    }

    destroyChart(canvasId) {
        if (this.charts[canvasId]) {
            this.charts[canvasId].destroy();
            delete this.charts[canvasId];
        }
    }

    renderDistributionPreview(canvasId, previewData) {
        this.destroyChart(canvasId);
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const hasUncertainty = previewData[0] && previewData[0].hasOwnProperty('p10');

        let datasets;
        if (hasUncertainty) {
            datasets = [
                {
                    label: 'Mean',
                    data: previewData.map(d => ({ x: d.month, y: d.mean })),
                    borderColor: '#2563eb',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: false,
                },
                {
                    label: 'P10',
                    data: previewData.map(d => ({ x: d.month, y: d.p10 })),
                    borderColor: 'rgba(37,99,235,0.3)',
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: '+1',
                    backgroundColor: 'rgba(37,99,235,0.1)',
                },
                {
                    label: 'P90',
                    data: previewData.map(d => ({ x: d.month, y: d.p90 })),
                    borderColor: 'rgba(37,99,235,0.3)',
                    borderWidth: 1,
                    pointRadius: 0,
                    fill: false,
                },
            ];
        } else {
            datasets = [
                {
                    label: 'Value',
                    data: previewData.map(d => ({ x: d.month, y: d.value })),
                    borderColor: '#16a34a',
                    borderWidth: 2,
                    pointRadius: 0,
                    fill: true,
                    backgroundColor: 'rgba(22,163,74,0.1)',
                },
            ];
        }

        this.charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: true, position: 'top', labels: { boxWidth: 12, font: { size: 11 } } } },
                scales: {
                    x: { type: 'linear', title: { display: true, text: 'Month', font: { size: 11 } } },
                    y: { title: { display: true, text: 'Value', font: { size: 11 } } },
                },
            },
        });
    }

    renderCombinedCashflowChart(canvasId, streamDetails, streamMeta) {
        this.destroyChart(canvasId);
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');

        const revenueColors = [
            '#16a34a', '#22c55e', '#4ade80', '#86efac', '#059669', '#10b981',
        ];
        const costColors = [
            '#dc2626', '#ef4444', '#f87171', '#fca5a5', '#b91c1c', '#e11d48',
        ];

        let revIdx = 0;
        let costIdx = 0;
        const datasets = [];

        streamMeta.forEach(meta => {
            const cfs = streamDetails[meta.id];
            if (!cfs) return;

            const isRevenue = meta.type === 'REVENUE';
            const color = isRevenue ? revenueColors[revIdx++ % revenueColors.length] : costColors[costIdx++ % costColors.length];

            datasets.push({
                label: meta.name,
                data: cfs.map((v, i) => ({ x: i, y: v })),
                borderColor: color,
                borderWidth: 2,
                pointRadius: 0,
                fill: false,
            });
        });

        this.charts[canvasId] = new Chart(ctx, {
            type: 'line',
            data: { datasets },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: true,
                        position: 'top',
                        labels: { boxWidth: 12, font: { size: 11 } },
                    },
                },
                scales: {
                    x: { type: 'linear', title: { display: true, text: 'Month', font: { size: 11 } } },
                    y: { title: { display: true, text: 'Cashflow ($)', font: { size: 11 } } },
                },
            },
        });
    }

    renderCashflowChart(canvasId, cashflows) {
        this.destroyChart(canvasId);
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const labels = cashflows.map((_, i) => i);

        const colors = cashflows.map(v => v >= 0 ? 'rgba(22,163,74,0.7)' : 'rgba(220,38,38,0.7)');

        this.charts[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [{ label: 'Monthly Cashflow', data: cashflows, backgroundColor: colors }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { title: { display: true, text: 'Month' } },
                    y: { title: { display: true, text: 'Cashflow ($)' } },
                },
            },
        });
    }

    renderNPVDistribution(canvasId, npvData, xLabel) {
        this.destroyChart(canvasId);
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');
        const isIRR = xLabel && xLabel.includes('IRR');
        const bins = this.createHistogramBins(npvData, isIRR);

        this.charts[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: bins.labels,
                datasets: [{
                    label: 'Frequency',
                    data: bins.frequencies,
                    backgroundColor: 'rgba(37,99,235,0.6)',
                    borderColor: 'rgba(37,99,235,0.8)',
                    borderWidth: 1,
                }],
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { title: { display: true, text: xLabel || 'NPV ($)' }, ticks: { maxTicksLimit: 10 } },
                    y: { title: { display: true, text: 'Frequency' } },
                },
            },
        });
    }

    renderTornadoChart(canvasId, sensitivityData) {
        this.destroyChart(canvasId);
        const canvas = document.getElementById(canvasId);
        if (!canvas) return;

        const ctx = canvas.getContext('2d');

        this.charts[canvasId] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: sensitivityData.map(d => d.parameter_name),
                datasets: [{
                    label: 'NPV Swing ($)',
                    data: sensitivityData.map(d => d.swing),
                    backgroundColor: sensitivityData.map((_, i) => {
                        const colors = [
                            'rgba(220,38,38,0.7)', 'rgba(234,88,12,0.7)', 'rgba(202,138,4,0.7)',
                            'rgba(22,163,74,0.7)', 'rgba(37,99,235,0.7)', 'rgba(124,58,237,0.7)',
                        ];
                        return colors[i % colors.length];
                    }),
                    borderWidth: 1,
                }],
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: {
                    x: { title: { display: true, text: 'NPV Swing ($)' } },
                },
            },
        });
    }

    createHistogramBins(data, isPercent = false) {
        const dataMin = Math.min(...data);
        const dataMax = Math.max(...data);
        if (dataMin === dataMax) {
            const label = isPercent ? (dataMin * 100).toFixed(1) + '%' : dataMin.toFixed(0);
            return { labels: [label], frequencies: [data.length] };
        }

        // Compute IQR-based display range (wide Tukey fences: 3×IQR)
        const sorted = [...data].sort((a, b) => a - b);
        const q1 = sorted[Math.floor(sorted.length * 0.25)];
        const q3 = sorted[Math.floor(sorted.length * 0.75)];
        const iqr = q3 - q1;
        const fenceLow = Math.max(dataMin, q1 - 3 * iqr);
        const fenceHigh = Math.min(dataMax, q3 + 3 * iqr);

        // Adaptive bin count: Rice rule capped at 50
        const adaptiveBins = Math.min(50, Math.ceil(2 * Math.pow(data.length, 1 / 3)));
        const effectiveBins = Math.max(adaptiveBins, 5);

        const hasLowOutliers = fenceLow > dataMin;
        const hasHighOutliers = fenceHigh < dataMax;

        const binWidth = (fenceHigh - fenceLow) / effectiveBins;
        const frequencies = Array(effectiveBins).fill(0);
        const labels = [];

        const formatLabel = (value, prefix = '') => {
            if (isPercent) {
                return prefix + (value * 100).toFixed(1) + '%';
            }
            return prefix + '$' + (value / 1000).toFixed(0) + 'k';
        };

        for (let i = 0; i < effectiveBins; i++) {
            const binStart = fenceLow + i * binWidth;
            let prefix = '';
            if (i === 0 && hasLowOutliers) prefix = '\u2264';
            if (i === effectiveBins - 1 && hasHighOutliers) prefix = '\u2265';
            labels.push(formatLabel(binStart, prefix));
        }

        // Assign data to bins, folding outliers into edge bins
        data.forEach(value => {
            if (value <= fenceLow) {
                frequencies[0]++;
            } else if (value >= fenceHigh) {
                frequencies[effectiveBins - 1]++;
            } else {
                const binIndex = Math.min(Math.floor((value - fenceLow) / binWidth), effectiveBins - 1);
                frequencies[binIndex]++;
            }
        });

        return { labels, frequencies };
    }
}

const chartManager = new ChartManager();

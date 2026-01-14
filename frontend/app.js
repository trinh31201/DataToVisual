const API_URL = 'http://localhost:8000/api/v1';
let chart = null;

function setQuestion(text) {
    document.getElementById('question').value = text;
}

async function submitQuery() {
    const question = document.getElementById('question').value.trim();
    if (!question) return;

    // Show loading, hide others
    document.getElementById('loading').classList.remove('hidden');
    document.getElementById('result').classList.add('hidden');
    document.getElementById('error').classList.add('hidden');

    try {
        const response = await fetch(`${API_URL}/query`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question })
        });

        document.getElementById('loading').classList.add('hidden');

        if (!response.ok) {
            const error = await response.json();
            showError(error.detail || `Error: ${response.status}`);
            return;
        }

        const data = await response.json();
        showResult(data);
    } catch (err) {
        document.getElementById('loading').classList.add('hidden');
        showError('Failed to connect to API. Make sure the backend is running.');
    }
}

/**
 * Convert raw data from API to Chart.js format
 * @param {Object[]} rows - Array of row objects
 * @returns {Object} Chart.js data format {labels, datasets}
 */
function toChartData(rows) {
    if (!rows || rows.length === 0) {
        return { labels: [], datasets: [] };
    }

    // Extract columns from first row
    const columns = Object.keys(rows[0]);

    // First column is labels, rest are datasets
    const labelColumn = columns[0];
    const dataColumns = columns.slice(1);

    const labels = rows.map(row => String(row[labelColumn]));

    const datasets = dataColumns.map(col => ({
        label: col.replace(/_/g, ' ').replace(/\b\w/g, c => c.toUpperCase()),
        data: rows.map(row => Number(row[col]) || 0)
    }));

    return { labels, datasets };
}

function showResult(data) {
    document.getElementById('result').classList.remove('hidden');
    const chartData = toChartData(data.rows);
    renderChart(data.chart_type, chartData);
}

function showError(message) {
    document.getElementById('error').textContent = message;
    document.getElementById('error').classList.remove('hidden');
}

function renderChart(type, data) {
    const ctx = document.getElementById('chart').getContext('2d');

    // Destroy previous chart
    if (chart) {
        chart.destroy();
    }

    const colors = [
        'rgba(54, 162, 235, 0.8)',
        'rgba(255, 99, 132, 0.8)',
        'rgba(75, 192, 192, 0.8)',
        'rgba(255, 206, 86, 0.8)',
        'rgba(153, 102, 255, 0.8)',
    ];

    const datasets = data.datasets.map((ds, i) => ({
        ...ds,
        backgroundColor: type === 'pie' ? colors : colors[i % colors.length],
        borderColor: type === 'line' ? colors[i % colors.length] : undefined,
        borderWidth: type === 'line' ? 2 : 1,
        fill: false,
    }));

    chart = new Chart(ctx, {
        type: type,
        data: {
            labels: data.labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'top',
                }
            },
            scales: type !== 'pie' ? {
                y: {
                    beginAtZero: true
                }
            } : {}
        }
    });
}

// Allow Enter key to submit
document.getElementById('question').addEventListener('keypress', (e) => {
    if (e.key === 'Enter') submitQuery();
});

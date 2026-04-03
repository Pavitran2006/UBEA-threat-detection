// Update Time
function updateTime() {
    const timeEl = document.getElementById('current-time');
    if (timeEl) {
        const now = new Date();
        timeEl.innerText = now.toLocaleTimeString();
    }
}
setInterval(updateTime, 1000);
updateTime();

// Initialize Charts if elements exist
document.addEventListener('DOMContentLoaded', () => {
    const loginCtx = document.getElementById('loginChart');
    if (loginCtx) {
        new Chart(loginCtx.getContext('2d'), {
            type: 'line',
            data: {
                labels: ['00:00', '04:00', '08:00', '12:00', '16:00', '20:00'],
                datasets: [{
                    label: 'Requests',
                    data: [12, 19, 3, 5, 2, 3],
                    borderColor: '#38bdf8',
                    tension: 0.4,
                    fill: true,
                    backgroundColor: 'rgba(56, 189, 248, 0.1)'
                }]
            },
            options: {
                responsive: true,
                plugins: { legend: { display: false } },
                scales: {
                    y: { grid: { color: 'rgba(255,255,255,0.05)' }, border: { display: false }, ticks: { color: '#94a3b8' } },
                    x: { grid: { display: false }, border: { display: false }, ticks: { color: '#94a3b8' } }
                }
            }
        });
    }

    const riskCtx = document.getElementById('riskChart');
    if (riskCtx) {
        new Chart(riskCtx.getContext('2d'), {
            type: 'doughnut',
            data: {
                labels: ['Low', 'Medium', 'High', 'Critical'],
                datasets: [{
                    data: [65, 20, 10, 5],
                    backgroundColor: ['#22c55e', '#f59e0b', '#f97316', '#ef4444'],
                    borderWidth: 0
                }]
            },
            options: {
                responsive: true,
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: { color: '#94a3b8', padding: 20, usePointStyle: true }
                    }
                }
            }
        });
    }
});

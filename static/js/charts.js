(function () {
  if (typeof Chart === 'undefined') return;

  Chart.defaults.font.family = "'IBM Plex Mono', ui-monospace, monospace";
  Chart.defaults.color = '#93A0BC';
  Chart.defaults.borderColor = 'rgba(255,255,255,.06)';

  const catEl = document.getElementById('categoryChart');
  if (catEl && typeof categoryLabels !== 'undefined') {
    new Chart(catEl, {
      type: 'bar',
      data: {
        labels: categoryLabels,
        datasets: [{
          label: '취약 건수',
          data: categoryVuln,
          backgroundColor: 'rgba(239,68,68,.55)',
          borderRadius: 4,
          barThickness: 22,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10.5 } } },
          y: { beginAtZero: true, grid: { color: 'rgba(255,255,255,.05)' } },
        },
      },
    });
  }

  const trendEl = document.getElementById('trendChart');
  if (trendEl && typeof trendLabels !== 'undefined') {
    new Chart(trendEl, {
      type: 'line',
      data: {
        labels: trendLabels,
        datasets: [{
          label: '평균 보안점수',
          data: trendValues,
          borderColor: '#2DD4BF',
          backgroundColor: 'rgba(45,212,191,.12)',
          fill: true,
          tension: 0.35,
          pointRadius: 0,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 }, maxTicksLimit: 8 } },
          y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,.05)' } },
        },
      },
    });
  }

  const histEl = document.getElementById('historyChart');
  if (histEl && typeof historyLabels !== 'undefined') {
    new Chart(histEl, {
      type: 'line',
      data: {
        labels: historyLabels,
        datasets: [{
          label: '보안점수',
          data: historyValues,
          borderColor: '#2DD4BF',
          backgroundColor: 'rgba(45,212,191,.12)',
          fill: true,
          tension: 0.35,
          pointRadius: 2,
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        plugins: { legend: { display: false } },
        scales: {
          x: { grid: { display: false }, ticks: { font: { size: 10 }, maxTicksLimit: 10 } },
          y: { min: 0, max: 100, grid: { color: 'rgba(255,255,255,.05)' } },
        },
      },
    });
  }
})();

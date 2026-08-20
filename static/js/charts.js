(function () {
  if (typeof Chart === 'undefined') return;

  Chart.defaults.font.family = "'IBM Plex Mono', ui-monospace, monospace";
  Chart.defaults.color = '#93A0BC';
  Chart.defaults.borderColor = 'rgba(255,255,255,.06)';

  const catEl = document.getElementById('categoryChart');
  if (catEl && typeof categoryLabels !== 'undefined') {
    // 카테고리별로 색을 다르게 줘서 도넛 조각이 서로 구분되게 한다 (앱 전체에서
    // 이미 쓰는 색 토큰을 그대로 재사용 - 새 팔레트를 따로 만들지 않는다).
    const catColors = ['#2C4C8C', '#E11D2E', '#E8650E', '#6E56CF', '#16A34A', '#B7871A'];
    new Chart(catEl, {
      type: 'doughnut',
      data: {
        labels: categoryLabels,
        datasets: [{
          label: '취약 건수',
          data: categoryVuln,
          backgroundColor: categoryLabels.map((_, i) => catColors[i % catColors.length]),
          borderColor: '#fff',
          borderWidth: 2,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: 'right',
            labels: { boxWidth: 10, boxHeight: 10, font: { size: 11.5 }, padding: 10 },
          },
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

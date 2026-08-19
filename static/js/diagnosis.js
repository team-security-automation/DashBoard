(function () {
  const box = document.getElementById('progressBox');
  const bar = document.getElementById('progressBar');
  const label = document.getElementById('progressLabel');
  const count = document.getElementById('progressCount');
  const servers = document.getElementById('progressServers');
  if (!box) return;

  function poll(runId) {
    box.style.display = 'block';
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/diagnosis/status/${runId}`);
        const data = await res.json();
        const pct = data.total ? Math.round((data.completed / data.total) * 100) : 0;
        bar.style.width = pct + '%';
        count.textContent = `${data.completed} / ${data.total}`;
        servers.innerHTML = data.servers.slice(0, data.completed)
          .map((s) => `<span>${s} 완료</span>`).join('');

        if (data.status === 'completed') {
          label.textContent = '진단 완료';
          clearInterval(timer);
          setTimeout(() => window.location.reload(), 900);
        } else {
          label.textContent = '진단 진행 중...';
        }
      } catch (e) {
        clearInterval(timer);
      }
    }, 500);
  }

  if (window.ACTIVE_RUN_ID) {
    poll(window.ACTIVE_RUN_ID);
  }

  const form = document.getElementById('scanForm');
  if (form) {
    form.addEventListener('submit', () => {
      box.style.display = 'block';
      label.textContent = '진단 요청 전송 중...';
    });
  }
})();

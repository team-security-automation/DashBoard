(function () {
  const grid = document.getElementById('reviewGrid');
  const empty = document.getElementById('reviewEmpty');
  const pendingEl = document.getElementById('pendingCount');
  const avgEl = document.getElementById('avgScore');
  if (!grid) return;

  function tweenNumber(el, from, to, decimals) {
    const textNode = el.firstChild;
    const duration = 550;
    const start = performance.now();
    el.classList.add('pulse');
    setTimeout(() => el.classList.remove('pulse'), duration);

    function frame(now) {
      const t = Math.min(1, (now - start) / duration);
      const eased = 1 - Math.pow(1 - t, 3);
      const value = from + (to - from) * eased;
      textNode.nodeValue = decimals ? value.toFixed(decimals) : Math.round(value).toString();
      if (t < 1) requestAnimationFrame(frame);
      else textNode.nodeValue = decimals ? to.toFixed(decimals) : to.toString();
    }
    requestAnimationFrame(frame);
  }

  grid.addEventListener('click', async (e) => {
    const btn = e.target.closest('button[data-outcome]');
    if (!btn) return;
    const card = btn.closest('.review-card');
    const outcome = btn.dataset.outcome;
    const id = card.dataset.id;

    card.querySelectorAll('button').forEach((b) => (b.disabled = true));

    try {
      const res = await fetch(`/review/${id}/decide`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ result: outcome }),
      });
      const data = await res.json();
      if (!res.ok || !data.ok) throw new Error(data.error || '처리에 실패했습니다');

      const prevPending = parseInt(pendingEl.firstChild.nodeValue, 10);
      const prevAvg = parseFloat(avgEl.firstChild.nodeValue);
      tweenNumber(pendingEl, prevPending, data.pending_count, 0);
      tweenNumber(avgEl, prevAvg, data.avg_score, 1);

      card.classList.add('removing');
      setTimeout(() => {
        card.remove();
        if (data.pending_count === 0) empty.classList.add('is-visible');
      }, 300);
    } catch (err) {
      card.querySelectorAll('button').forEach((b) => (b.disabled = false));
    }
  });
})();

(function () {
  const box = document.getElementById('progressBox');
  const bar = document.getElementById('progressBar');
  const label = document.getElementById('progressLabel');
  const count = document.getElementById('progressCount');
  const sub = document.getElementById('progressSub');
  const servers = document.getElementById('progressServers');
  if (!box) return;

  function poll(runId) {
    box.style.display = 'block';
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/diagnosis/status/${runId}`);
        const data = await res.json();
        const pct = data.percent != null ? Math.round(data.percent)
          : (data.total ? Math.round((data.completed / data.total) * 100) : 0);
        bar.style.width = pct + '%';
        // 서버 몇 대 끝났는지보다 "지금 서버에서 몇 번째 점검 항목까지 돌았는지"가
        // 훨씬 체감되는 진행 신호라 헤드라인 카운트를 항목 단위로 우선 보여준다.
        if (data.status !== 'completed' && data.item_total) {
          count.textContent = `${data.item_done} / ${data.item_total}개 항목`;
        } else {
          count.textContent = `${data.completed} / ${data.total}대 서버`;
        }
        servers.innerHTML = data.servers.slice(0, data.completed)
          .map((s) => `<span>${s} 완료</span>`).join('');

        if (sub) {
          if (data.status !== 'completed' && data.current_server && data.category) {
            sub.style.display = 'block';
            sub.textContent = `${data.current_server} · ${data.category} 확인 중`
              + ` (카테고리 ${data.cat_index}/${data.cat_total} · 서버 ${data.completed}/${data.total}대 완료)`;
          } else {
            sub.style.display = 'none';
          }
        }

        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
          label.textContent = data.status === 'completed' ? '진단 완료'
            : data.status === 'cancelled' ? '진단 중지됨'
            : '진단 실패';
          clearInterval(timer);
          const goBack = () => { window.location.href = window.location.pathname; };
          if (data.status === 'failed' && window.showFailReason) {
            // 실패 원인을 읽을 시간을 주기 위해, 팝업을 닫을 때 새로고침하도록 콜백을 넘긴다.
            // (바로 새로고침하면 팝업이 뜨자마자 사라져서 원인을 못 읽음)
            window.showFailReason(data.fail_reason, goBack);
          } else {
            // URL에 run_id가 남아있으면 새로고침 후에도 끝난 run을 다시 폴링해서
            // reload가 반복되므로, 쿼리스트링 없는 순수 페이지로 이동한다.
            setTimeout(goBack, 900);
          }
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

(function () {
  const box = document.getElementById('progressBox');
  const bar = document.getElementById('progressBar');
  const label = document.getElementById('progressLabel');
  const count = document.getElementById('progressCount');
  const lanes = document.getElementById('progressLanes');
  const doneBox = document.getElementById('progressDone');
  if (!box) return;

  const STATUS_BADGE = {
    '대기': '<span class="badge badge-neutral">대기</span>',
    '진행중': '<span class="badge badge-warn">진행중</span>',
    '완료': '<span class="badge badge-good">완료</span>',
    '실패': '<span class="badge badge-vuln">실패</span>',
  };

  function renderLanes(hostsDetail) {
    if (!lanes) return;
    lanes.innerHTML = hostsDetail.map((h) => {
      const stepText = h.step_total ? `${h.step_index}/${h.step_total}단계` : '';
      const itemText = h.item_total ? ` · ${h.item_done}/${h.item_total}항목` : '';
      const taskText = h.task ? h.task : (h.status === '실패' ? (h.reason || '') : '');
      return `
        <div class="progress-lane">
          <div class="progress-lane-head">
            <strong>${h.hostname}</strong>
            ${STATUS_BADGE[h.status] || h.status}
          </div>
          <div class="bar-track progress-track progress-track-sm">
            <div class="bar-fill ${h.status === '실패' ? 'bar-vuln' : 'bar-accent'}" style="width:${h.percent}%"></div>
          </div>
          <div class="progress-lane-sub mono">${stepText}${itemText}${taskText ? ' · ' + taskText : ''}</div>
        </div>`;
    }).join('');
  }

  function poll(runId) {
    box.style.display = 'block';
    if (doneBox) doneBox.style.display = 'none';
    const timer = setInterval(async () => {
      try {
        const res = await fetch(`/diagnosis/status/${runId}`);
        const data = await res.json();
        const pct = data.percent != null ? Math.round(data.percent) : 0;
        bar.style.width = pct + '%';
        count.textContent = `${data.completed} / ${data.total}대 서버`;
        renderLanes(data.hosts_detail || []);

        if (data.status === 'completed' || data.status === 'failed' || data.status === 'cancelled') {
          clearInterval(timer);
          const ok = (data.hosts_detail || []).filter((h) => h.status === '완료').length;
          const fail = (data.hosts_detail || []).filter((h) => h.status === '실패').length;
          label.textContent = data.status === 'completed' ? '진단 완료'
            : data.status === 'cancelled' ? '진단 중지됨'
            : '진단 실패';

          // 예전엔 완료되면 0.9초 뒤 조용히 초기 화면으로 새로고침해서
          // "다 됐는지도 모르게 사라진다"는 문제가 있었다. 이제는 결과 요약을
          // 화면에 그대로 남겨두고, 사용자가 확인 버튼을 눌러야 새로고침한다.
          // "결과 보러가는 과정이 어색하다"는 피드백대로, 방금 진단한 서버로 바로
          // 들어가는 링크를 여기서 직접 만들어준다 (대시보드로 보내고 거기서 다시
          // 서버를 찾아 들어가야 하는 우회 없이).
          if (doneBox) {
            doneBox.style.display = 'block';
            const links = data.server_links || [];
            const linksHtml = links.length === 1
              ? `<a href="/servers/${links[0].id}" class="btn btn-primary btn-sm">${links[0].hostname} 결과 보기</a>`
              : links.map((s) => `<a href="/servers/${s.id}" class="btn btn-ghost btn-sm">${s.hostname}</a>`).join(' ');
            doneBox.innerHTML = `
              <p><strong>${ok}대 성공${fail ? `, ${fail}대 실패` : ''}</strong> — 진단 결과가 저장되었습니다.</p>
              <div class="form-actions" style="border-top:none; padding-top:0; flex-wrap:wrap">
                ${linksHtml}
                <button type="button" class="btn btn-ghost btn-sm" id="progressDoneOk">닫기</button>
              </div>`;
            document.getElementById('progressDoneOk').addEventListener('click', () => {
              window.location.href = window.location.pathname;
            });
          }
          if (data.status === 'failed' && window.showFailReason) {
            window.showFailReason(data.fail_reason, null);
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
      if (doneBox) doneBox.style.display = 'none';
      label.textContent = '진단 요청 전송 중...';
    });
  }
})();

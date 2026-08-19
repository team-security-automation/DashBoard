# -*- coding: utf-8 -*-
from flask import Blueprint, render_template, request
from flask_login import login_required

from models import Server, ScoreSnapshot, ActionHistory

history_bp = Blueprint("history", __name__, url_prefix="/history")


@history_bp.route("/")
@login_required
def index():
    servers = Server.query.order_by(Server.id).all()
    sel = request.args.get("server_id", "all")

    if sel == "all":
        snaps = ScoreSnapshot.query.filter_by(server_id=None).order_by(ScoreSnapshot.snapshot_date).all()
        title = "전체 서버 평균"
    else:
        sid = int(sel)
        snaps = (ScoreSnapshot.query.filter_by(server_id=sid)
                 .order_by(ScoreSnapshot.snapshot_date).all())
        srv = Server.query.get_or_404(sid)
        title = srv.hostname

    labels = [s.snapshot_date.strftime("%m/%d") for s in snaps]
    values = [s.score for s in snaps]

    # 서버별 최신 점수(비교용 미니 차트)
    compare = []
    for srv in servers:
        last = (ScoreSnapshot.query.filter_by(server_id=srv.id)
                .order_by(ScoreSnapshot.snapshot_date.desc()).first())
        if last:
            compare.append(dict(hostname=srv.hostname, score=last.score, grade=last.grade))

    action_history = ActionHistory.query.order_by(ActionHistory.performed_at.desc()).limit(30).all()

    return render_template(
        "history.html", servers=servers, sel=sel, title=title,
        labels=labels, values=values, compare=compare, action_history=action_history,
    )

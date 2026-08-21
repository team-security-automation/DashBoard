# -*- coding: utf-8 -*-
import os
from datetime import timedelta
from flask import Flask
from flask_login import current_user
from config import Config
from extensions import db, login_manager

KST = timedelta(hours=9)


def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)
    login_manager.init_app(app)

    from models import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    from blueprints.auth import auth_bp
    from blueprints.dashboard import dashboard_bp
    from blueprints.servers import servers_bp
    from blueprints.diagnosis import diagnosis_bp
    from blueprints.approvals import approvals_bp
    from blueprints.history import history_bp
    from blueprints.reports import reports_bp
    from blueprints.review import review_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(servers_bp)
    app.register_blueprint(diagnosis_bp)
    app.register_blueprint(approvals_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(review_bp)

    # DB에는 datetime.utcnow()(UTC)로 저장하지만 화면에는 KST로 보여줘야 하므로,
    # 템플릿에서 strftime 전에 거치는 변환 필터를 하나 둔다. (DB 컬럼을 KST로
    # 바꾸면 서버 간 로그 비교 시 혼란스러워지니 저장은 계속 UTC로 유지)
    @app.template_filter("kst")
    def to_kst(dt):
        return dt + KST if dt else dt

    # 템플릿에서 사용할 전역값
    from models import RISK_LABEL

    @app.context_processor
    def inject_globals():
        # 사이드바 "진단·조치" 배지 - 역할마다 처리할 게 다르다: 실무자는 수동확인+
        # 실행/완료처리 대기, 승인자는 승인 대기. diagnosis.index()의 "처리할 항목"
        # 큐와 같은 개념을 세자면 매 페이지 로드마다 승인요청 전체를 훑어 최신건만
        # 골라야 해서(무겁다), 배지는 간단 집계만 쓰고 정확한 중복 제거는 큐 화면
        # 자체에서 한다.
        pending_count = 0
        manual_review_count = 0
        if getattr(current_user, "is_authenticated", False):
            from models import ApprovalRequest
            from blueprints.review import pending_manual_count
            if current_user.can_decide_approval():
                pending_count = ApprovalRequest.query.filter_by(status="pending").count()
            if current_user.can_run_diagnosis():
                manual_review_count = pending_manual_count() + (
                    ApprovalRequest.query.filter_by(status="approved", executed_at=None).count()
                )
        return dict(RISK_LABEL=RISK_LABEL, pending_count=pending_count,
                    manual_review_count=manual_review_count)

    with app.app_context():
        db_path = app.config["SQLALCHEMY_DATABASE_URI"]
        need_seed = False
        if db_path.startswith("sqlite:///"):
            file_path = db_path.replace("sqlite:///", "")
            need_seed = not os.path.exists(file_path)
        db.create_all()
        if need_seed:
            from seed_data import seed
            seed()
            print(">> 최초 실행 감지: 데모 시드 데이터를 생성했습니다.")

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5050)

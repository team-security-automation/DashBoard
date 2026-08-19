# -*- coding: utf-8 -*-
"""
Flask 확장 객체 모음.
app.py에서 순환 임포트를 피하기 위해 별도 모듈로 분리한다.
"""
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager

db = SQLAlchemy()
login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.login_message = "로그인이 필요합니다."
login_manager.login_message_category = "warning"

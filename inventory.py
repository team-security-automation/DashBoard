# -*- coding: utf-8 -*-
"""
Ansible 인벤토리 생성
----------------------
WBS "1.1 Ansible 인벤토리 설계 착수 - YAML, OS별 그룹화" 항목에 대응한다.

대시보드에 등록된 Server 목록을 읽어 OS 계열별로 그룹화한 YAML 인벤토리를
생성한다. 진단 실행 버튼을 누를 때마다(또는 서버 등록/수정 시) 최신 상태로
다시 생성해서 항상 DB와 인벤토리가 어긋나지 않게 한다.

생성 결과 예시:
    all:
      children:
        rocky_linux:
          hosts:
            rocky01:
              ansible_host: 10.0.10.11
              ansible_user: ansible
              ansible_port: 22
              ansible_ssh_private_key_file: /etc/ansible/keys/rocky01.pem
              ansible_become: true
              server_id: 1
        ubuntu:
          hosts:
            ubuntu01: {...}
"""
import os
import yaml

from models import Server

ANSIBLE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ansible")
INVENTORY_PATH = os.path.join(ANSIBLE_DIR, "inventory", "hosts.yml")


def _os_group(server: Server) -> str:
    """OS 계열명을 Ansible 그룹명으로 정규화 (Rocky Linux -> rocky_linux 등)"""
    return server.os_family.strip().lower().replace(" ", "_")


def generate_inventory(server_ids=None, path=None):
    """
    등록된 서버(또는 server_ids로 지정된 서버만)를 기준으로 YAML 인벤토리를 생성한다.
    반환값: 생성된 인벤토리 파일의 절대경로
    """
    path = path or INVENTORY_PATH
    query = Server.query
    if server_ids:
        query = query.filter(Server.id.in_(server_ids))
    servers = query.order_by(Server.id).all()

    groups = {}
    for s in servers:
        if not s.ip or not s.ssh_key_path:
            # SSH 키 경로가 없는 서버는 인벤토리에서 제외하고 넘어간다.
            # (실행 화면에서 "SSH 설정 누락" 경고로 알려주는 편이 좋다 - diagnosis.py 참고)
            continue
        group = _os_group(s)
        groups.setdefault(group, {"hosts": {}})
        groups[group]["hosts"][s.hostname] = {
            "ansible_host": s.ip,
            "ansible_user": s.ssh_user or "ansible",
            "ansible_port": s.ssh_port or 22,
            "ansible_ssh_private_key_file": s.ssh_key_path,
            "ansible_become": bool(s.ssh_become),
            "server_id": s.id,  # 결과 JSON을 어느 Server row에 매핑할지 대조용
        }

    inventory = {"all": {"children": groups}} if groups else {"all": {"hosts": {}}}

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(inventory, f, allow_unicode=True, sort_keys=False)

    return path


def servers_missing_ssh_config():
    """SSH 키 경로가 비어있어 인벤토리에서 빠지는 서버 목록 (경고 표시용)"""
    return Server.query.filter(
        (Server.ssh_key_path.is_(None)) | (Server.ssh_key_path == "")
    ).all()
